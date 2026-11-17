"""Vendor-agnostic transport for every model call the pipeline makes.

One entry point, ``complete(prompt, model, **params)``, resolves a model
identifier to one of six providers and dispatches to its adapter, writing
one record per call under ``.hotdocs/calls/``.  The setup helpers
``hotdocs init`` builds on live here too.
"""

from __future__ import annotations

import functools
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

USER_AGENT = "hotdocs-llm-endpoint/1.0 (Python urllib)"

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

_CONFIG_KEYS = ("provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth")
_SECRET_WORDS = ("key", "token", "password", "secret", "credential")
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_LLM_HEADER = re.compile(r"\[\s*llm\s*\]\s*(#.*)?")

_BARE_AUTH_MESSAGE = (
    "claude command failed (auth): ANTHROPIC_API_KEY is set, so claude used it "
    "instead of your claude.ai login; unset it, or set auth = \"login\" in "
    "hotdocs.toml's [llm] table"
)
_CLI_MARKERS = (
    ("rate_limit", ("rate limit", "rate_limit", "429")),
    ("auth", ("auth", "login", "api key", "401", "403")),
    ("timeout", ("timed out", "timeout")),
)
_CHECK_PROMPT = "Reply with the single word: ok"


class ModelResolutionError(Exception):
    """A model identifier resolves to no usable provider (R-ENDPOINT-002)."""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def parse_model(model: str) -> tuple[str | None, str]:
    prefix, sep, rest = model.partition(":")
    if sep and prefix in PROVIDERS:
        if not rest:
            raise ModelResolutionError(
                f"model {model!r} names provider {prefix!r} but no model after it"
            )
        return prefix, rest
    return None, model


def resolve_provider(model: str, config: dict | None = None) -> dict:
    provider, name = parse_model(model)
    config = config or {}
    configured = config.get("provider")
    if configured is not None and configured not in PROVIDERS:
        raise ModelResolutionError(
            f"hotdocs.toml names unknown provider {configured!r}"
        )
    if provider is None:
        if configured is not None:
            provider = configured
        elif name.startswith("claude-"):
            provider = "claude-cli"
        else:
            raise ModelResolutionError(
                f"model {model!r} names no provider and hotdocs.toml configures none; "
                "write it as <provider>:<model>"
            )
    settings = config if provider == configured else {}
    info = PROVIDERS[provider]
    base_url = settings.get("base_url") or info["default_base_url"]
    if info["needs_base_url"] and not base_url:
        raise ModelResolutionError(f"provider {provider} needs a base_url in hotdocs.toml")
    return {
        "provider": provider,
        "model": name,
        "base_url": base_url,
        "api_key_env": settings.get("api_key_env") or info["default_api_key_env"],
        "timeout_seconds": settings.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS,
        "auth": settings.get("auth"),
    }


def resolve_backend_name(model: str) -> str:
    provider, name = parse_model(model)
    if provider is None and name.startswith("claude-"):
        return "anthropic"
    return resolve_provider(model)["provider"]


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def _validate(table: dict) -> dict:
    for name in table:
        if name not in _CONFIG_KEYS:
            if any(word in name.lower() for word in _SECRET_WORDS):
                raise ValueError(
                    f"[llm] entry {name!r} looks like a secret: hotdocs.toml must never hold a secret"
                )
            raise ValueError(f"unknown [llm] entry {name!r}")
    provider = table.get("provider")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError(
            "[llm] provider is missing or not one of: " + ", ".join(PROVIDERS)
        )
    model = table.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("[llm] model is required")
    base_url = table.get("base_url") or None
    if base_url is not None and (
        not isinstance(base_url, str) or not base_url.startswith(("http://", "https://"))
    ):
        raise ValueError("[llm] base_url must be an http(s) URL")
    api_key_env = table.get("api_key_env") or None
    if api_key_env is not None:
        if not isinstance(api_key_env, str) or not _ENV_NAME.fullmatch(api_key_env):
            raise ValueError(
                "[llm] api_key_env must be the name of an environment variable, never the key itself"
            )
        if api_key_env in os.environ.values():
            raise ValueError(
                "[llm] api_key_env looks like a pasted key: it must be the name of an "
                "environment variable, never the key itself"
            )
    timeout = table.get("timeout_seconds")
    if timeout is not None and (
        isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 300
    ):
        raise ValueError("[llm] timeout_seconds must be a whole number of seconds, at least 300")
    auth = table.get("auth")
    if auth is not None:
        if provider != "claude-cli":
            raise ValueError("[llm] auth applies to the claude-cli provider only")
        if auth not in ("login", "key"):
            raise ValueError('[llm] auth must be "login" or "key"')
    if provider == "claude-cli" and (base_url or api_key_env):
        raise ValueError("[llm] claude-cli takes no base_url or api_key_env")
    if PROVIDERS[provider]["needs_base_url"] and base_url is None:
        raise ValueError(f"[llm] provider {provider} needs a base_url")
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout,
        "auth": auth,
    }


def load_config(config_path: Path | None = None) -> dict | None:
    if config_path is None:
        named = os.environ.get("VAR_HOTDOCS_CONFIG")
        if named:
            config_path = Path(named)
            if not config_path.is_file():
                raise ValueError(f"VAR_HOTDOCS_CONFIG names {named}, which does not exist")
        else:
            config_path = Path("hotdocs.toml")
    path = Path(config_path)
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        raise ValueError(f"{path} is not valid TOML") from None
    table = data.get("llm")
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ValueError(f"{path}: [llm] must be a table")
    return _validate(table)


def save_config(
    config_path: Path,
    provider: str,
    model: str,
    base_url: str | None = None,
    api_key_env: str | None = None,
    timeout_seconds: int | None = None,
    auth: str | None = None,
) -> None:
    config = _validate({
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
        "auth": auth,
    })
    lines = ["[llm]"]
    for key in _CONFIG_KEYS:
        value = config[key]
        if value is not None:
            rendered = str(value) if isinstance(value, int) else json.dumps(value)
            lines.append(f"{key} = {rendered}")
    path = Path(config_path)
    kept = []
    if path.is_file():
        skipping = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                skipping = _LLM_HEADER.fullmatch(stripped) is not None
            if not skipping:
                kept.append(line)
    text = "\n".join(kept).rstrip("\n")
    if text:
        text += "\n\n"
    text += "\n".join(lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# HTTP providers
# --------------------------------------------------------------------------

def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return True
    return isinstance(exc, urllib.error.URLError) and isinstance(
        exc.reason, (socket.timeout, TimeoutError)
    )


def _classify(exc: BaseException, provider: str | None) -> dict:
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        if code in (401, 403):
            category = "auth"
        elif code == 429:
            category = "rate_limit"
        elif code in (408, 504):
            category = "timeout"
        elif code == 400 and provider == "gemini" and _gemini_key_invalid(exc):
            category = "auth"
        else:
            category = "network"
        return {"category": category, "message": f"HTTP {code} from backend"}
    if _is_timeout(exc):
        return {"category": "timeout", "message": "request timed out"}
    return {"category": "network", "message": "request to backend failed"}


def _gemini_key_invalid(exc: urllib.error.HTTPError) -> bool:
    body = exc.read().decode("utf-8", "replace").lower()
    return "api key not valid" in body or "api_key_invalid" in body


def _post_json(url: str, headers: dict, payload: dict, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        raw = reply.read()
    return json.loads(raw)


def _pick(params: dict, mapping: dict) -> dict:
    return {dst: params[src] for src, dst in mapping.items() if src in params}


def _bearer(key):
    return {"Authorization": f"Bearer {key}"} if key else {}


def _messages(prompt: str) -> list:
    return [{"role": "user", "content": prompt}]


def _build_anthropic(prompt, model, base, key, params):
    payload = {
        "model": model,
        "max_tokens": params.get("max_tokens", 32000),
        "messages": _messages(prompt),
        **_pick(params, {"temperature": "temperature"}),
    }
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return base.rstrip("/") + "/v1/messages", headers, payload, _extract_anthropic


def _extract_anthropic(data):
    return "".join(block["text"] for block in data["content"] if block.get("type") == "text")


def _build_openai(prompt, model, base, key, params):
    payload = {
        "model": model,
        "messages": _messages(prompt),
        **_pick(params, {"max_tokens": "max_completion_tokens", "temperature": "temperature"}),
    }
    return base.rstrip("/") + "/chat/completions", _bearer(key), payload, _extract_openai


def _build_openai_compatible(prompt, model, base, key, params):
    payload = {
        "model": model,
        "messages": _messages(prompt),
        **_pick(params, {"max_tokens": "max_tokens", "temperature": "temperature"}),
    }
    return base.rstrip("/") + "/chat/completions", _bearer(key), payload, _extract_openai


def _extract_openai(data):
    return data["choices"][0]["message"]["content"]


def _build_gemini(prompt, model, base, key, params):
    name = model.removeprefix("models/")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": _pick(
            params, {"max_tokens": "maxOutputTokens", "temperature": "temperature"}
        ),
    }
    url = f"{base.rstrip('/')}/v1beta/models/{name}:generateContent"
    return url, {"x-goog-api-key": key}, payload, _extract_gemini


def _extract_gemini(data):
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(part.get("text", "") for part in parts if not part.get("thought"))


def _build_ollama(prompt, model, base, key, params):
    payload = {
        "model": model,
        "messages": _messages(prompt),
        "stream": False,
        "options": _pick(
            params,
            {"max_tokens": "num_predict", "temperature": "temperature", "num_ctx": "num_ctx"},
        ),
    }
    return base.rstrip("/") + "/api/chat", _bearer(key), payload, _extract_ollama


def _extract_ollama(data):
    return data["message"]["content"]


def _call_http(builder, prompt: str, resolved: dict, params: dict):
    provider = resolved["provider"]
    var = resolved["api_key_env"]
    key = os.environ.get(var) if var else None
    if PROVIDERS[provider]["default_api_key_env"] and not key:
        return None, {"category": "auth", "message": f"{var} is not set"}
    url, headers, payload, extract = builder(prompt, resolved["model"], resolved["base_url"], key, params)
    try:
        data = _post_json(url, headers, payload, resolved["timeout_seconds"])
        text = extract(data)
    except Exception as exc:
        return None, _classify(exc, provider)
    if not text:
        return None, {"category": "network", "message": "reply held no text"}
    return text, None


# --------------------------------------------------------------------------
# claude-cli provider
# --------------------------------------------------------------------------

def _cli_error(category: str, auth, flag: str) -> dict:
    if category == "auth" and auth is None and flag == "--bare":
        return {"category": "auth", "message": _BARE_AUTH_MESSAGE}
    return {"category": category, "message": f"claude command failed ({category})"}


def _cli_failure(text: str, auth, flag: str) -> dict:
    lowered = text.lower()
    for category, markers in _CLI_MARKERS:
        if any(marker in lowered for marker in markers):
            return _cli_error(category, auth, flag)
    return _cli_error("network", auth, flag)


def _stream_events(stdout: str):
    events = []
    for line in stdout.splitlines():
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


def _call_claude_cli(prompt: str, resolved: dict, params: dict):
    auth = resolved["auth"]
    env = dict(os.environ)
    if auth == "login":
        flag = "--safe-mode"
        env.pop("ANTHROPIC_API_KEY", None)
    elif auth == "key":
        flag = "--bare"
    else:
        flag = "--bare" if os.environ.get("ANTHROPIC_API_KEY") else "--safe-mode"
    command = [
        "claude", "-p", "--model", resolved["model"], "--tools", "",
        "--output-format", "stream-json", "--verbose", flag,
    ]
    for name, value in params.items():
        command += ["--" + name.replace("_", "-"), str(value)]
    try:
        run = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=resolved["timeout_seconds"],
        )
    except subprocess.TimeoutExpired:
        return None, _cli_error("timeout", auth, flag)
    except OSError:
        return None, _cli_error("network", auth, flag)
    events = _stream_events(run.stdout)
    if events is None:
        if run.returncode == 0:
            return run.stdout, None
        return None, _cli_failure(run.stdout + "\n" + run.stderr, auth, flag)
    failed = [e for e in events if e.get("type") == "result" and e.get("is_error")]
    if run.returncode != 0 or failed:
        text = " ".join(str(e.get("result", "")) for e in failed) + "\n" + run.stderr
        return None, _cli_failure(text, auth, flag)
    reply = "".join(
        block.get("text", "")
        for event in events
        if event.get("type") == "assistant"
        for block in event["message"]["content"]
        if block.get("type") == "text"
    )
    return reply, None


_ADAPTERS = {
    "claude-cli": _call_claude_cli,
    "anthropic": functools.partial(_call_http, _build_anthropic),
    "openai": functools.partial(_call_http, _build_openai),
    "openai-compatible": functools.partial(_call_http, _build_openai_compatible),
    "gemini": functools.partial(_call_http, _build_gemini),
    "ollama": functools.partial(_call_http, _build_ollama),
}


# --------------------------------------------------------------------------
# Entry point and call log
# --------------------------------------------------------------------------

def _log_call(response: dict) -> None:
    now = datetime.now(timezone.utc)
    record = {
        "timestamp": now.isoformat(),
        "model": response["model"],
        "backend": response["backend"],
    }
    if response["model_call_error"] is None:
        record["text_present"] = response["text"] is not None
    else:
        record["model_call_error"] = response["model_call_error"]
    directory = Path(".hotdocs") / "calls"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{now:%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex}.json"
    (directory / name).write_text(json.dumps(record), encoding="utf-8")


def complete(prompt: str, model: str, *, backend=None, **params) -> dict:
    if backend is None:
        try:
            config = load_config()
        except ValueError as exc:
            raise ModelResolutionError(str(exc)) from None
        resolved = resolve_provider(model, config)
        backend_name = resolved["provider"]
        text, error = _ADAPTERS[backend_name](prompt, resolved, params)
    else:
        backend_name = getattr(backend, "__name__", type(backend).__name__)
        try:
            reply = backend(prompt, model, **params)
        except Exception as exc:
            text, error = None, _classify(exc, None)
        else:
            text = _get(reply, "text")
            error = _get(reply, "model_call_error")
            backend_name = _get(reply, "backend") or backend_name
            if error is not None:
                error = {"category": _get(error, "category"), "message": _get(error, "message")}
    response = {
        "text": text,
        "model": model,
        "backend": backend_name,
        "model_call_error": error,
    }
    _log_call(response)
    return response


# --------------------------------------------------------------------------
# Setup helpers
# --------------------------------------------------------------------------

def _probe_ollama(base_url: str) -> bool:
    request = urllib.request.Request(base_url + "/api/tags", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=1):
            return True
    except OSError:
        return False


def detect_providers(env: dict | None = None, probe_ollama: bool = True) -> list[dict]:
    env = os.environ if env is None else env
    found = []
    for provider, info in PROVIDERS.items():
        var = info["default_api_key_env"]
        if provider == "claude-cli":
            available = shutil.which("claude", path=env.get("PATH", "")) is not None
            reason = "claude command found on PATH" if available else "claude command not found on PATH"
        elif var:
            available = bool(env.get(var, "").strip())
            reason = f"{var} is set" if available else f"{var} is not set"
        elif info["needs_base_url"]:
            available = False
            reason = "needs a base_url"
        elif not probe_ollama:
            available = False
            reason = "Ollama server not probed"
        else:
            base = info["default_base_url"]
            available = _probe_ollama(base)
            reason = (
                f"Ollama server answering at {base}" if available
                else f"no Ollama server answering at {base}"
            )
        found.append({
            "provider": provider,
            "available": available,
            "reason": reason,
            "suggested_model": info["suggested_model"],
            "api_key_env": var,
        })
    return found


def check_connection(
    provider: str,
    model: str,
    base_url: str | None = None,
    api_key_env: str | None = None,
    timeout_seconds: int = 30,
    auth: str | None = None,
) -> dict:
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}")
    info = PROVIDERS[provider]
    base = base_url or info["default_base_url"]
    if info["needs_base_url"] and not base:
        raise ValueError(f"provider {provider} needs a base_url")
    resolved = {
        "provider": provider,
        "model": model,
        "base_url": base,
        "api_key_env": api_key_env or info["default_api_key_env"],
        "timeout_seconds": timeout_seconds,
        "auth": auth,
    }
    params = {} if provider == "claude-cli" else {"max_tokens": 1024}
    _text, error = _ADAPTERS[provider](_CHECK_PROMPT, resolved, params)
    return {"ok": error is None, "error": error}
