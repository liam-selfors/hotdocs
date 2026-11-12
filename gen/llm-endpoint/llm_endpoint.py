"""LLM Endpoint: the single, vendor-agnostic transport for every model call.

`complete(prompt, model, **params)` resolves a model identifier to one of
six providers (`claude-cli`, `anthropic`, `openai`, `openai-compatible`,
`gemini`, `ollama`), makes exactly one bounded call, classifies any
failure, logs one record under `.hotdocs/calls/`, and returns a
`ModelResponse` dict. Credentials are read only from the process
environment and never leave this module.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tomllib
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 600
MIN_TIMEOUT_SECONDS = 300
USER_AGENT = "hotdocs-llm-endpoint/1.0 (python-urllib)"

PROVIDERS = {
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "anthropic": {
        "default_base_url": "https://api.anthropic.com",
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai": {
        "default_base_url": "https://api.openai.com/v1",
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-6-astra",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
    "gemini": {
        "default_base_url": "https://generativelanguage.googleapis.com",
        "default_api_key_env": "GEMINI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gemini-4-argon",
    },
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.2",
    },
}

_CONFIG_ENTRIES = ("provider", "model", "base_url", "api_key_env", "timeout_seconds")
_SECRET_NAME = re.compile(r"key|token|password|passwd|secret|credential", re.IGNORECASE)
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_LLM_HEADER = re.compile(r"\s*\[\s*llm\s*\]\s*(#.*)?")
_PROBE_PROMPT = "Reply with the single word: ok"

_CLI_CATEGORIES = (
    ("rate_limit", ("rate limit", "rate_limit", "429")),
    ("auth", ("auth", "login", "api key", "401", "403")),
    ("timeout", ("timed out", "timeout")),
)


class ModelResolutionError(Exception):
    """A model identifier resolves to no usable provider (R-ENDPOINT-002)."""


class _CallError(Exception):
    """A classified provider failure raised inside an adapter."""

    def __init__(self, category, message):
        super().__init__(message)
        self.category = category
        self.message = message


# --------------------------------------------------------------------------
# Resolution (R-ENDPOINT-002)
# --------------------------------------------------------------------------


def parse_model(model):
    """Split an identifier into `(provider, model)`; provider None when bare."""
    prefix, sep, rest = model.partition(":")
    if sep and prefix in PROVIDERS:
        if not rest:
            raise ModelResolutionError(
                f"model identifier {model!r} names provider {prefix!r} but no model after it"
            )
        return prefix, rest
    return None, model


def resolve_provider(model, config=None):
    """Resolve an identifier to `{provider, model, base_url, api_key_env, timeout_seconds}`."""
    provider, name = parse_model(model)
    if config is not None and config.get("provider") not in PROVIDERS:
        raise ModelResolutionError("hotdocs.toml configures no known provider")
    settings = {}
    if provider is None:
        if config is not None:
            provider = config["provider"]
            settings = config
        elif name.startswith("claude-"):
            provider = "claude-cli"
        else:
            raise ModelResolutionError(
                f"model {model!r} names no provider: write it as <provider>:<model> "
                f"with one of {', '.join(PROVIDERS)}, or configure one in hotdocs.toml"
            )
    elif config is not None and config.get("provider") == provider:
        settings = config
    spec = PROVIDERS[provider]
    base_url = settings.get("base_url") or spec["default_base_url"]
    if spec["needs_base_url"] and not base_url:
        raise ModelResolutionError(f"provider {provider!r} needs a base_url in hotdocs.toml")
    return {
        "provider": provider,
        "model": name,
        "base_url": base_url,
        "api_key_env": settings.get("api_key_env") or spec["default_api_key_env"],
        "timeout_seconds": settings.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS,
    }


def resolve_backend_name(model):
    """Compatibility label: `"anthropic"` for a bare `claude-*` name."""
    provider, name = parse_model(model)
    if provider is None and name.startswith("claude-"):
        return "anthropic"
    return resolve_provider(model)["provider"]


# --------------------------------------------------------------------------
# Entry point (R-ENDPOINT-001)
# --------------------------------------------------------------------------


def complete(prompt, model, *, backend=None, **params):
    """Make one model call and return a `ModelResponse` dict."""
    if backend is None:
        try:
            config = load_config()
        except ValueError as exc:
            raise ModelResolutionError(f"invalid hotdocs.toml: {exc}") from None
        resolved = resolve_provider(model, config)
        name = resolved["provider"]
        text, error = _dispatch(prompt, resolved, params)
    else:
        name, text, error = _call_injected(backend, prompt, model, params)
    response = {"text": text, "model": model, "backend": name, "model_call_error": error}
    _log_call(response)
    return response


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _backend_label(backend):
    return getattr(backend, "__name__", None) or type(backend).__name__


def _call_injected(backend, prompt, model, params):
    try:
        reply = backend(prompt, model, **params)
    except Exception as exc:
        return _backend_label(backend), None, _classify(exc)
    name = _get(reply, "backend") or _backend_label(backend)
    error = _get(reply, "model_call_error")
    if error is not None:
        return name, None, {"category": _get(error, "category"), "message": _get(error, "message")}
    text, error = _reply(_get(reply, "text"))
    return name, text, error


def _dispatch(prompt, resolved, params):
    try:
        text = _ADAPTERS[resolved["provider"]](prompt, resolved, params)
    except Exception as exc:
        return None, _classify(exc)
    return _reply(text)


def _reply(text):
    if not text:
        return None, {"category": "network", "message": "backend reply had no text"}
    return text, None


def _classify(exc):
    if isinstance(exc, _CallError):
        return {"category": exc.category, "message": exc.message}
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        if code in (401, 403):
            category = "auth"
        elif code == 429:
            category = "rate_limit"
        elif code in (408, 504):
            category = "timeout"
        else:
            category = "network"
        return {"category": category, "message": f"HTTP {code} from backend"}
    if isinstance(exc, (socket.timeout, TimeoutError, subprocess.TimeoutExpired)) or (
        isinstance(exc, urllib.error.URLError)
        and isinstance(exc.reason, (socket.timeout, TimeoutError))
    ):
        return {"category": "timeout", "message": "backend call timed out"}
    return {"category": "network", "message": "network failure calling backend"}


def _log_call(response):
    now = datetime.now(timezone.utc)
    record = {
        "timestamp": now.isoformat(),
        "model": response["model"],
        "backend": response["backend"],
    }
    if response["model_call_error"] is None:
        record["text_present"] = bool(response["text"])
    else:
        record["model_call_error"] = response["model_call_error"]
    directory = Path.cwd() / ".hotdocs" / "calls"
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex}.json"
    (directory / filename).write_text(json.dumps(record), encoding="utf-8")


# --------------------------------------------------------------------------
# Adapters (R-ENDPOINT-003, R-ENDPOINT-008)
# --------------------------------------------------------------------------


def _claude_cli(prompt, resolved, params):
    command = [
        "claude",
        "-p",
        "--model",
        resolved["model"],
        "--tools",
        "",
        "--output-format",
        "stream-json",
        "--verbose",
        "--bare" if os.environ.get("ANTHROPIC_API_KEY") else "--safe-mode",
    ]
    for key, value in params.items():
        command += ["--" + key.replace("_", "-"), str(value)]
    proc = subprocess.run(
        command,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=resolved["timeout_seconds"],
    )
    events = _parse_stream(proc.stdout)
    if events is None:
        if proc.returncode != 0:
            _raise_cli_failure(proc.stderr + proc.stdout)
        return proc.stdout
    failures = [e for e in events if e.get("type") == "result" and e.get("is_error")]
    if failures or proc.returncode != 0:
        _raise_cli_failure(" ".join(str(e.get("result", "")) for e in failures) + " " + proc.stderr)
    parts = []
    for event in events:
        if event.get("type") == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return "".join(parts)


def _parse_stream(output):
    events = []
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            return None
        if not isinstance(event, dict):
            return None
        events.append(event)
    return events or None


def _raise_cli_failure(detail):
    lowered = detail.lower()
    for category, markers in _CLI_CATEGORIES:
        if any(marker in lowered for marker in markers):
            raise _CallError(category, f"claude command failed ({category})")
    raise _CallError("network", "claude command failed (network)")


def _required_key(resolved):
    env_name = resolved["api_key_env"]
    key = os.environ.get(env_name)
    if not key:
        raise _CallError("auth", f"{env_name} is not set")
    return key


def _optional_key(resolved):
    env_name = resolved["api_key_env"]
    return os.environ.get(env_name) if env_name else None


def _bearer(key):
    return {"Authorization": f"Bearer {key}"} if key else {}


def _copy(params, target, name, dest=None):
    if name in params:
        target[dest or name] = params[name]


def _url(resolved, path):
    return resolved["base_url"].rstrip("/") + path


def _post_json(url, body, headers, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return reply.read()


def _answer(raw, extract):
    try:
        return extract(json.loads(raw))
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise _CallError("network", "unreadable reply from backend") from None


def _user_messages(prompt):
    return [{"role": "user", "content": prompt}]


def _anthropic(prompt, resolved, params):
    key = _required_key(resolved)
    body = {
        "model": resolved["model"],
        "max_tokens": params.get("max_tokens", 32000),
        "messages": _user_messages(prompt),
    }
    _copy(params, body, "temperature")
    raw = _post_json(
        _url(resolved, "/v1/messages"),
        body,
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        resolved["timeout_seconds"],
    )
    return _answer(
        raw, lambda d: "".join(b["text"] for b in d["content"] if b.get("type") == "text")
    )


def _openai_chat(prompt, resolved, params, key, token_field):
    body = {"model": resolved["model"], "messages": _user_messages(prompt)}
    _copy(params, body, "max_tokens", token_field)
    _copy(params, body, "temperature")
    raw = _post_json(
        _url(resolved, "/chat/completions"), body, _bearer(key), resolved["timeout_seconds"]
    )
    return _answer(raw, lambda d: d["choices"][0]["message"]["content"])


def _openai(prompt, resolved, params):
    return _openai_chat(prompt, resolved, params, _required_key(resolved), "max_completion_tokens")


def _openai_compatible(prompt, resolved, params):
    return _openai_chat(prompt, resolved, params, _optional_key(resolved), "max_tokens")


def _gemini(prompt, resolved, params):
    key = _required_key(resolved)
    name = resolved["model"]
    if name.startswith("models/"):
        name = name[len("models/"):]
    generation = {}
    _copy(params, generation, "max_tokens", "maxOutputTokens")
    _copy(params, generation, "temperature")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation,
    }
    try:
        raw = _post_json(
            _url(resolved, f"/v1beta/models/{name}:generateContent"),
            body,
            {"x-goog-api-key": key},
            resolved["timeout_seconds"],
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 400 and "api key not valid" in exc.read().decode("utf-8", "replace").lower():
            raise _CallError("auth", "API key not valid") from None
        raise
    return _answer(
        raw,
        lambda d: "".join(
            p["text"]
            for p in d["candidates"][0]["content"]["parts"]
            if "text" in p and not p.get("thought")
        ),
    )


def _ollama(prompt, resolved, params):
    options = {}
    _copy(params, options, "max_tokens", "num_predict")
    _copy(params, options, "temperature")
    _copy(params, options, "num_ctx")
    body = {
        "model": resolved["model"],
        "messages": _user_messages(prompt),
        "stream": False,
        "options": options,
    }
    raw = _post_json(
        _url(resolved, "/api/chat"),
        body,
        _bearer(_optional_key(resolved)),
        resolved["timeout_seconds"],
    )
    return _answer(raw, lambda d: d["message"]["content"])


_ADAPTERS = {
    "claude-cli": _claude_cli,
    "anthropic": _anthropic,
    "openai": _openai,
    "openai-compatible": _openai_compatible,
    "gemini": _gemini,
    "ollama": _ollama,
}


# --------------------------------------------------------------------------
# Configuration (R-ENDPOINT-007)
# --------------------------------------------------------------------------


def load_config(config_path=None):
    """Return the validated `[llm]` table, or None; raise ValueError when invalid."""
    if config_path is None:
        named = os.environ.get("VAR_HOTDOCS_CONFIG")
        if named:
            config_path = Path(named)
            if not config_path.is_file():
                raise ValueError(f"VAR_HOTDOCS_CONFIG names {named}, which does not exist")
        else:
            config_path = Path.cwd() / "hotdocs.toml"
    config_path = Path(config_path)
    if not config_path.is_file():
        return None
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{config_path} is not valid TOML: {exc}") from None
    table = data.get("llm")
    if table is None:
        return None
    return _validate_table(table)


def _validate_table(table):
    if not isinstance(table, dict):
        raise ValueError("[llm] must be a table")
    for entry in table:
        if entry not in _CONFIG_ENTRIES:
            if _SECRET_NAME.search(entry):
                raise ValueError(
                    f"hotdocs.toml must never hold a secret: entry {entry!r} looks like one; "
                    "name the environment variable that holds it in api_key_env instead"
                )
            raise ValueError(f"unknown entry {entry!r} in [llm]")
    provider = table.get("provider")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError(f"[llm] provider must be one of {', '.join(PROVIDERS)}")
    model = table.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("[llm] model is required")
    base_url = table.get("base_url") or None
    if base_url is not None and (
        not isinstance(base_url, str) or not re.match(r"https?://", base_url)
    ):
        raise ValueError("[llm] base_url must be an http(s) URL")
    if PROVIDERS[provider]["needs_base_url"] and base_url is None:
        raise ValueError(f"[llm] provider {provider!r} requires a base_url")
    api_key_env = table.get("api_key_env") or None
    if api_key_env is not None:
        if not isinstance(api_key_env, str) or not _ENV_NAME.fullmatch(api_key_env):
            raise ValueError(
                "[llm] api_key_env must be the name of an environment variable, "
                "never the key itself"
            )
        if api_key_env in os.environ.values():
            raise ValueError(
                "[llm] api_key_env equals an environment variable's value and looks like a "
                "pasted key: it must be the variable's name, never the key itself"
            )
    if provider == "claude-cli" and (base_url is not None or api_key_env is not None):
        raise ValueError("[llm] provider 'claude-cli' takes no base_url or api_key_env")
    timeout = table.get("timeout_seconds")
    if timeout is not None and (
        isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < MIN_TIMEOUT_SECONDS
    ):
        raise ValueError(f"[llm] timeout_seconds must be an integer of at least {MIN_TIMEOUT_SECONDS}")
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout,
    }


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    """Validate as `load_config` does, then replace only the file's `[llm]` table."""
    table = {"provider": provider, "model": model}
    for entry, value in (
        ("base_url", base_url),
        ("api_key_env", api_key_env),
        ("timeout_seconds", timeout_seconds),
    ):
        if value is not None:
            table[entry] = value
    config = _validate_table(table)
    lines = ["[llm]\n"]
    for entry in _CONFIG_ENTRIES:
        value = config[entry]
        if value is not None:
            lines.append(f"{entry} = {_toml_value(value)}\n")
    path = Path(config_path)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_replace_llm_table(existing, "".join(lines)), encoding="utf-8")


def _toml_value(value):
    return str(value) if isinstance(value, int) else json.dumps(value, ensure_ascii=False)


def _replace_llm_table(text, block):
    lines = text.splitlines(keepends=True)
    start = None
    for index, line in enumerate(lines):
        if _LLM_HEADER.fullmatch(line.rstrip("\r\n")):
            start = index
            break
    if start is None:
        if text and not text.endswith("\n"):
            text += "\n"
        return text + ("\n" if text else "") + block
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].lstrip().startswith("["):
            end = index
            break
    tail = "".join(lines[end:])
    return "".join(lines[:start]) + block + ("\n" + tail if tail else "")


# --------------------------------------------------------------------------
# Setup helpers (R-ENDPOINT-009)
# --------------------------------------------------------------------------


def detect_providers(env=None, probe_ollama=True):
    """Report, per provider, whether it looks usable now."""
    env = os.environ if env is None else env
    found = []
    for name, spec in PROVIDERS.items():
        key_env = spec["default_api_key_env"]
        if name == "claude-cli":
            available = shutil.which("claude", path=env.get("PATH") or "") is not None
            reason = "claude command found on PATH" if available else "claude command not found on PATH"
        elif key_env:
            available = bool((env.get(key_env) or "").strip())
            reason = f"{key_env} is set" if available else f"{key_env} is not set"
        elif spec["needs_base_url"]:
            available, reason = False, "needs the base_url of an OpenAI-compatible server"
        elif probe_ollama:
            available = _ollama_answers(spec["default_base_url"])
            reason = "Ollama server answered" if available else "no Ollama server answered"
        else:
            available, reason = False, "Ollama server not probed"
        found.append(
            {
                "provider": name,
                "available": available,
                "reason": reason,
                "suggested_model": spec["suggested_model"],
                "api_key_env": key_env,
            }
        )
    return found


def _ollama_answers(base_url):
    request = urllib.request.Request(base_url + "/api/tags", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=1):
            return True
    except Exception:
        return False


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    """Send one tiny real completion; return `{ok, error}`. Never logged."""
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}")
    spec = PROVIDERS[provider]
    if spec["needs_base_url"] and not base_url:
        raise ValueError(f"provider {provider!r} requires a base_url")
    resolved = {
        "provider": provider,
        "model": model,
        "base_url": base_url or spec["default_base_url"],
        "api_key_env": api_key_env or spec["default_api_key_env"],
        "timeout_seconds": timeout_seconds,
    }
    params = {} if provider == "claude-cli" else {"max_tokens": 1024}
    _text, error = _dispatch(_PROBE_PROMPT, resolved, params)
    return {"ok": error is None, "error": error}