"""Vendor-agnostic transport for every model call the pipeline makes.

One entry point, ``complete(prompt, model, **params)``, resolves a model
identifier to one of six provider adapters, makes exactly one bounded call,
classifies any failure, and records one line in ``.hotdocs/calls/``.
"""

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
ANTHROPIC_DEFAULT_MAX_TOKENS = 32000
USER_AGENT = "hotdocs-llm-endpoint/1.0 (Python urllib)"
CONFIG_ENV_VAR = "VAR_HOTDOCS_CONFIG"

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

_CONFIG_KEYS = ("provider", "model", "base_url", "api_key_env", "timeout_seconds")
_SECRET_HINTS = ("key", "token", "password", "passwd", "secret", "credential")
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_URL = re.compile(r"https?://\S+")
_TABLE_HEADER = re.compile(r"\[\[?[^\[\]]+\]\]?\s*(#.*)?")
_LLM_HEADER = re.compile(r"\[\s*llm\s*\]\s*(#.*)?")
_API_KEY_ENV_REFUSAL = (
    "[llm] api_key_env must be the name of an environment variable, "
    "never the key itself"
)


class ModelResolutionError(Exception):
    """A model identifier resolves to no usable provider (R-ENDPOINT-002)."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _error(category, message):
    return {"category": category, "message": message}


def _is_variable_name(value):
    return (
        isinstance(value, str)
        and _ENV_NAME.fullmatch(value) is not None
        and value not in os.environ.values()
    )


# ---------------------------------------------------------------------------
# Configuration (R-ENDPOINT-007)
# ---------------------------------------------------------------------------

def _validate_llm(table):
    for name in table:
        if name not in _CONFIG_KEYS:
            if any(hint in name.lower() for hint in _SECRET_HINTS):
                raise ValueError(
                    f"[llm] entry {name!r} looks like a secret: hotdocs.toml "
                    "must never hold a secret; name the environment variable "
                    "in api_key_env instead"
                )
            raise ValueError(f"[llm] has unknown entry {name!r}")

    provider = table.get("provider")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError(
            "[llm] provider is required and must be one of: "
            + ", ".join(PROVIDERS)
        )
    model = table.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("[llm] model is required")

    base_url = table.get("base_url") or None
    if base_url is not None and not (
        isinstance(base_url, str) and _URL.fullmatch(base_url)
    ):
        raise ValueError("[llm] base_url must be an http(s) URL")

    api_key_env = table.get("api_key_env") or None
    if api_key_env is not None and not _is_variable_name(api_key_env):
        raise ValueError(_API_KEY_ENV_REFUSAL)

    timeout_seconds = table.get("timeout_seconds")
    if timeout_seconds is not None and (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or timeout_seconds < MIN_TIMEOUT_SECONDS
    ):
        raise ValueError(
            f"[llm] timeout_seconds must be an integer of at least "
            f"{MIN_TIMEOUT_SECONDS}"
        )

    if provider == "claude-cli" and (base_url or api_key_env):
        raise ValueError("[llm] claude-cli takes no base_url or api_key_env")
    if PROVIDERS[provider]["needs_base_url"] and base_url is None:
        raise ValueError(f"[llm] provider {provider} requires base_url")

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
    }


def load_config(config_path=None):
    from_env = False
    if config_path is None:
        named = os.environ.get(CONFIG_ENV_VAR)
        if named:
            config_path, from_env = named, True
        else:
            config_path = Path.cwd() / "hotdocs.toml"
    path = Path(config_path)
    if not path.is_file():
        if from_env:
            raise ValueError(
                f"{CONFIG_ENV_VAR} names {path}, which does not exist"
            )
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path} is not valid TOML: {exc}") from None
    table = data.get("llm")
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ValueError("[llm] must be a table")
    return _validate_llm(table)


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None):
    settings = _validate_llm({
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
    })
    table_lines = ["[llm]"] + [
        f"{key} = {json.dumps(settings[key])}"
        for key in _CONFIG_KEYS
        if settings[key] is not None
    ]

    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    out, skipping, placed = [], False, False
    for line in existing:
        stripped = line.strip()
        if _TABLE_HEADER.fullmatch(stripped):
            skipping = _LLM_HEADER.fullmatch(stripped) is not None
            if skipping and not placed:
                out.extend(table_lines + [""])
                placed = True
        if not skipping:
            out.append(line)
    if not placed:
        if out and out[-1].strip():
            out.append("")
        out.extend(table_lines)
    while out and not out[-1].strip():
        out.pop()
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Resolution (R-ENDPOINT-002)
# ---------------------------------------------------------------------------

def parse_model(model):
    prefix, sep, rest = model.partition(":")
    if sep and prefix in PROVIDERS:
        if not rest:
            raise ModelResolutionError(
                f"model identifier {model!r} names provider {prefix!r} "
                "but no model after it"
            )
        return prefix, rest
    return None, model


def resolve_provider(model, config=None):
    provider, name = parse_model(model)
    if config is not None:
        try:
            config = _validate_llm(config)
        except ValueError as exc:
            raise ModelResolutionError(f"invalid hotdocs.toml: {exc}") from None
    if provider is None:
        if config is not None:
            provider = config["provider"]
        elif name.startswith("claude-"):
            provider = "claude-cli"
        else:
            raise ModelResolutionError(
                f"model {model!r} names no provider: write it as "
                "<provider>:<model> or configure one in hotdocs.toml"
            )
    settings = config if config is not None and config["provider"] == provider else {}
    entry = PROVIDERS[provider]
    base_url = settings.get("base_url") or entry["default_base_url"]
    if base_url is None and entry["needs_base_url"]:
        raise ModelResolutionError(
            f"provider {provider} needs a base_url, set in hotdocs.toml"
        )
    return {
        "provider": provider,
        "model": name,
        "base_url": base_url,
        "api_key_env": settings.get("api_key_env") or entry["default_api_key_env"],
        "timeout_seconds": settings.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS,
    }


def resolve_backend_name(model):
    provider, name = parse_model(model)
    if provider is None and name.startswith("claude-"):
        return "anthropic"
    return resolve_provider(model)["provider"]


# ---------------------------------------------------------------------------
# Failure classification (R-ENDPOINT-004)
# ---------------------------------------------------------------------------

def _status_error(code):
    if code in (401, 403):
        category = "auth"
    elif code == 429:
        category = "rate_limit"
    elif code in (408, 504):
        category = "timeout"
    else:
        category = "network"
    return _error(category, f"{code} from backend")


def _is_timeout(exc):
    timeouts = (socket.timeout, TimeoutError)
    return isinstance(exc, timeouts) or (
        isinstance(exc, urllib.error.URLError)
        and isinstance(exc.reason, timeouts)
    )


def _classify_exception(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return _status_error(exc.code)
    if _is_timeout(exc):
        return _error("timeout", "request timed out")
    return _error("network", "network failure")


# ---------------------------------------------------------------------------
# HTTP adapters (R-ENDPOINT-003, R-ENDPOINT-008)
# ---------------------------------------------------------------------------

def _required_key(env_name):
    key = os.environ.get(env_name, "")
    if not key.strip():
        if _is_variable_name(env_name):
            message = f"missing API key: environment variable {env_name} is not set"
        else:
            message = "missing API key: " + _API_KEY_ENV_REFUSAL
        return None, _error("auth", message)
    return key, None


def _optional_bearer(env_name):
    key = os.environ.get(env_name) if env_name else None
    return {"Authorization": f"Bearer {key}"} if key else {}


def _base(resolved):
    return resolved["base_url"].rstrip("/")


def _exchange(provider, url, headers, body, timeout, extract):
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            raw = reply.read()
    except urllib.error.HTTPError as exc:
        if provider == "gemini" and exc.code == 400:
            said = (exc.read() or b"").decode("utf-8", "replace").lower()
            if "api key not valid" in said or "api_key_invalid" in said:
                return None, _error("auth", "API key not valid")
        return None, _status_error(exc.code)
    except Exception as exc:
        return None, _classify_exception(exc)
    try:
        text = extract(json.loads(raw))
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return None, _error("network", "unreadable reply body")
    if not isinstance(text, str) or not text:
        return None, _error("network", "reply had no text")
    return text, None


def _messages(prompt):
    return [{"role": "user", "content": prompt}]


def _anthropic(resolved, prompt, params):
    key, error = _required_key(resolved["api_key_env"])
    if error:
        return None, error
    body = {
        "model": resolved["model"],
        "max_tokens": params.get("max_tokens", ANTHROPIC_DEFAULT_MAX_TOKENS),
        "messages": _messages(prompt),
    }
    if "temperature" in params:
        body["temperature"] = params["temperature"]
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return _exchange(
        "anthropic", _base(resolved) + "/v1/messages", headers, body,
        resolved["timeout_seconds"],
        lambda data: "".join(
            block["text"] for block in data["content"] if block.get("type") == "text"
        ),
    )


def _openai_style(provider, resolved, prompt, params, headers, token_field):
    body = {"model": resolved["model"], "messages": _messages(prompt)}
    if "max_tokens" in params:
        body[token_field] = params["max_tokens"]
    if "temperature" in params:
        body["temperature"] = params["temperature"]
    return _exchange(
        provider, _base(resolved) + "/chat/completions", headers, body,
        resolved["timeout_seconds"],
        lambda data: data["choices"][0]["message"]["content"],
    )


def _openai(resolved, prompt, params):
    key, error = _required_key(resolved["api_key_env"])
    if error:
        return None, error
    return _openai_style(
        "openai", resolved, prompt, params,
        {"Authorization": f"Bearer {key}"}, "max_completion_tokens",
    )


def _openai_compatible(resolved, prompt, params):
    return _openai_style(
        "openai-compatible", resolved, prompt, params,
        _optional_bearer(resolved["api_key_env"]), "max_tokens",
    )


def _gemini(resolved, prompt, params):
    key, error = _required_key(resolved["api_key_env"])
    if error:
        return None, error
    name = resolved["model"].removeprefix("models/")
    generation_config = {}
    if "max_tokens" in params:
        generation_config["maxOutputTokens"] = params["max_tokens"]
    if "temperature" in params:
        generation_config["temperature"] = params["temperature"]
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }
    return _exchange(
        "gemini", f"{_base(resolved)}/v1beta/models/{name}:generateContent",
        {"x-goog-api-key": key}, body, resolved["timeout_seconds"],
        lambda data: "".join(
            part.get("text", "")
            for part in data["candidates"][0]["content"]["parts"]
            if not part.get("thought")
        ),
    )


def _ollama(resolved, prompt, params):
    options = {}
    if "max_tokens" in params:
        options["num_predict"] = params["max_tokens"]
    if "temperature" in params:
        options["temperature"] = params["temperature"]
    if "num_ctx" in params:
        options["num_ctx"] = params["num_ctx"]
    body = {
        "model": resolved["model"],
        "messages": _messages(prompt),
        "stream": False,
        "options": options,
    }
    return _exchange(
        "ollama", _base(resolved) + "/api/chat",
        _optional_bearer(resolved["api_key_env"]), body,
        resolved["timeout_seconds"],
        lambda data: data["message"]["content"],
    )


# ---------------------------------------------------------------------------
# claude-cli adapter (R-ENDPOINT-003)
# ---------------------------------------------------------------------------

def _read_stream(output):
    events = []
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            return output, False
        if not isinstance(event, dict) or "type" not in event:
            return output, False
        events.append(event)
    if not events:
        return output, False
    parts, failed = [], False
    for event in events:
        if event["type"] == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
        elif event["type"] == "result" and event.get("is_error") is True:
            failed = True
    return "".join(parts), failed


def _command_error(reported):
    lowered = reported.lower()
    if any(hint in lowered for hint in ("rate limit", "rate_limit", "usage limit")):
        return _error("rate_limit", "claude command reported a rate limit")
    if any(hint in lowered for hint in (
        "invalid api key", "authentication", "unauthorized", "not logged in", "/login",
    )):
        return _error("auth", "claude command reported an authentication failure")
    return _error("network", "claude command failed")


def _claude_cli(resolved, prompt, params):
    command = [
        "claude", "-p",
        "--model", resolved["model"],
        "--tools", "",
        "--bare" if os.environ.get("ANTHROPIC_API_KEY") else "--safe-mode",
        "--output-format", "stream-json", "--verbose",
    ]
    for name, value in params.items():
        command += ["--" + name.replace("_", "-"), str(value)]
    try:
        done = subprocess.run(
            command, input=prompt, capture_output=True, text=True,
            timeout=resolved["timeout_seconds"],
        )
    except subprocess.TimeoutExpired:
        return None, _error("timeout", "claude command timed out")
    except OSError:
        return None, _error("network", "claude command could not be run")
    text, failed = _read_stream(done.stdout)
    if failed or done.returncode != 0:
        return None, _command_error(done.stdout + done.stderr)
    if not text:
        return None, _error("network", "reply had no text")
    return text, None


_ADAPTERS = {
    "claude-cli": _claude_cli,
    "anthropic": _anthropic,
    "openai": _openai,
    "openai-compatible": _openai_compatible,
    "gemini": _gemini,
    "ollama": _ollama,
}


# ---------------------------------------------------------------------------
# Call log (R-ENDPOINT-006)
# ---------------------------------------------------------------------------

def _log_call(response):
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
    directory = Path.cwd() / ".hotdocs" / "calls"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}.json"
    (directory / name).write_text(json.dumps(record), encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point (R-ENDPOINT-001)
# ---------------------------------------------------------------------------

def complete(prompt, model, *, backend=None, **params):
    if backend is None:
        try:
            config = load_config()
        except ValueError as exc:
            raise ModelResolutionError(f"invalid hotdocs.toml: {exc}") from None
        resolved = resolve_provider(model, config)
        backend_name = resolved["provider"]
        text, error = _ADAPTERS[backend_name](resolved, prompt, params)
    else:
        backend_name = getattr(backend, "__name__", type(backend).__name__)
        try:
            reply = backend(prompt, model, **params)
        except Exception as exc:
            text, error = None, _classify_exception(exc)
        else:
            text = _get(reply, "text")
            raw_error = _get(reply, "model_call_error")
            error = None if raw_error is None else {
                "category": _get(raw_error, "category"),
                "message": _get(raw_error, "message"),
            }
            backend_name = _get(reply, "backend") or backend_name
    response = {
        "text": text,
        "model": model,
        "backend": backend_name,
        "model_call_error": error,
    }
    _log_call(response)
    return response


# ---------------------------------------------------------------------------
# Setup helpers (R-ENDPOINT-009)
# ---------------------------------------------------------------------------

def _probe_ollama():
    url = PROVIDERS["ollama"]["default_base_url"] + "/api/tags"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=1):
            pass
    except Exception:
        return False, f"no Ollama server answered at {url}"
    return True, f"Ollama server answered at {url}"


def detect_providers(env=None, probe_ollama=True):
    env = os.environ if env is None else env
    found = []
    for provider, entry in PROVIDERS.items():
        key_env = entry["default_api_key_env"]
        if provider == "claude-cli":
            available = shutil.which("claude", path=env.get("PATH", "")) is not None
            reason = "claude command on PATH" if available else "claude command not on PATH"
        elif key_env is not None:
            available = bool(env.get(key_env, "").strip())
            reason = f"{key_env} is set" if available else f"{key_env} is not set"
        elif provider == "ollama":
            if probe_ollama:
                available, reason = _probe_ollama()
            else:
                available, reason = False, "Ollama server not probed"
        else:
            available, reason = False, "needs the base_url of a running server"
        found.append({
            "provider": provider,
            "available": available,
            "reason": reason,
            "suggested_model": entry["suggested_model"],
            "api_key_env": key_env,
        })
    return found


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30):
    if provider not in PROVIDERS:
        raise ValueError(
            f"unknown provider {provider!r}; expected one of: " + ", ".join(PROVIDERS)
        )
    entry = PROVIDERS[provider]
    base = base_url or entry["default_base_url"]
    if entry["needs_base_url"] and not base:
        raise ValueError(f"provider {provider} needs a base_url")
    resolved = {
        "provider": provider,
        "model": model,
        "base_url": base,
        "api_key_env": api_key_env or entry["default_api_key_env"],
        "timeout_seconds": timeout_seconds,
    }
    params = {} if provider == "claude-cli" else {"max_tokens": 1024}
    _text, error = _ADAPTERS[provider](
        resolved, "Reply with the single word OK.", params
    )
    return {"ok": error is None, "error": error}
