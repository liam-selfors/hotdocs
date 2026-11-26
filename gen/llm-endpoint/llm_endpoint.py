"""llm-endpoint: one vendor-agnostic transport for every model call.

Entry point: ``complete(prompt, model, **params) -> ModelResponse`` (a plain
dict).  A model identifier is ``<provider>:<model>`` or a bare name resolved
through the optional ``hotdocs.toml`` ``[llm]`` table.
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

_CONFIG_KEYS = ("provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth")
_SECRET_MARKERS = ("key", "token", "password", "passwd", "secret", "credential")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LLM_HEADER_RE = re.compile(r"^\[\s*llm\s*\]\s*(#.*)?$")

_MESSAGES = {
    "network": "network error reaching backend",
    "auth": "authentication with backend failed",
    "rate_limit": "rate limited by backend",
    "timeout": "backend call timed out",
}

_BARE_AUTH_MESSAGE = (
    "claude command failed (auth): ANTHROPIC_API_KEY is set, so claude used it "
    "instead of your claude.ai login; unset it, or set auth = \"login\" in "
    "hotdocs.toml's [llm] table"
)


class ModelResolutionError(Exception):
    """A model identifier resolves to no usable provider (R-ENDPOINT-002)."""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _error(category, message=None):
    return {"category": category, "message": message or _MESSAGES[category]}


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def parse_model(model):
    head, sep, tail = model.partition(":")
    if sep and head in PROVIDERS:
        if not tail:
            raise ModelResolutionError(f"model identifier {model!r} names no model after its provider prefix")
        return head, tail
    return None, model


def resolve_provider(model, config=None):
    provider, name = parse_model(model)
    settings = {}
    if provider is None:
        if config is not None:
            provider = config.get("provider")
            if provider not in PROVIDERS:
                raise ModelResolutionError(f"hotdocs.toml names an unknown provider {provider!r}")
            settings = config
        elif name.startswith("claude-"):
            provider = "claude-cli"
        else:
            raise ModelResolutionError(
                f"model {model!r} has no provider prefix and no hotdocs.toml configures one"
            )
    elif config is not None and config.get("provider") == provider:
        settings = config
    defaults = PROVIDERS[provider]
    base_url = settings.get("base_url") or defaults["default_base_url"]
    if defaults["needs_base_url"] and not base_url:
        raise ModelResolutionError(f"provider {provider!r} requires a base_url in hotdocs.toml")
    return {
        "provider": provider,
        "model": name,
        "base_url": base_url,
        "api_key_env": settings.get("api_key_env") or defaults["default_api_key_env"],
        "timeout_seconds": settings.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS,
        "auth": settings.get("auth"),
    }


def resolve_backend_name(model):
    provider, name = parse_model(model)
    if provider is not None:
        return provider
    if name.startswith("claude-"):
        return "anthropic"
    raise ModelResolutionError(f"model {model!r} has no provider prefix")


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def _validate(table):
    for key in table:
        if key not in _CONFIG_KEYS:
            if any(marker in key.lower() for marker in _SECRET_MARKERS):
                raise ValueError(
                    f"hotdocs.toml must never hold a secret: remove the {key!r} entry from [llm]; "
                    "name the environment variable holding the key in api_key_env instead"
                )
            raise ValueError(f"hotdocs.toml [llm] has an unknown entry {key!r}")

    provider = table.get("provider")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError(f"hotdocs.toml [llm] provider must be one of {', '.join(PROVIDERS)}")

    model = table.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("hotdocs.toml [llm] model is required")

    base_url = table.get("base_url")
    if base_url == "":
        base_url = None
    if base_url is not None:
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            raise ValueError("hotdocs.toml [llm] base_url must be an http(s) URL")
        if provider == "claude-cli":
            raise ValueError("hotdocs.toml [llm] base_url is not used by claude-cli")
    if PROVIDERS[provider]["needs_base_url"] and base_url is None:
        raise ValueError(f"hotdocs.toml [llm] base_url is required for {provider}")

    api_key_env = table.get("api_key_env")
    if api_key_env == "":
        api_key_env = None
    if api_key_env is not None:
        if not isinstance(api_key_env, str) or not _ENV_NAME_RE.match(api_key_env):
            raise ValueError(
                "hotdocs.toml [llm] api_key_env must be the name of an environment variable, "
                "never the key itself"
            )
        if api_key_env in os.environ.values():
            raise ValueError(
                "hotdocs.toml [llm] api_key_env looks like a pasted key: it must name the "
                "environment variable, never the key itself"
            )
        if provider == "claude-cli":
            raise ValueError("hotdocs.toml [llm] api_key_env is not used by claude-cli")

    timeout = table.get("timeout_seconds")
    if timeout is not None:
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < MIN_TIMEOUT_SECONDS:
            raise ValueError(
                f"hotdocs.toml [llm] timeout_seconds must be an integer of at least {MIN_TIMEOUT_SECONDS}"
            )

    auth = table.get("auth")
    if auth is not None:
        if provider != "claude-cli":
            raise ValueError("hotdocs.toml [llm] auth is used only by claude-cli")
        if auth not in ("login", "key"):
            raise ValueError('hotdocs.toml [llm] auth must be "login" or "key"')

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout,
        "auth": auth,
    }


def load_config(config_path=None):
    if config_path is None:
        named = os.environ.get("VAR_HOTDOCS_CONFIG")
        if named:
            path = Path(named)
            if not path.is_file():
                raise ValueError(f"VAR_HOTDOCS_CONFIG names {named}, which does not exist")
        else:
            path = Path.cwd() / "hotdocs.toml"
    else:
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
        raise ValueError(f"{path}: llm must be a table")
    return _validate(table)


def _toml_value(value):
    if isinstance(value, str):
        return json.dumps(value)
    return str(value)


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    given = {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
        "auth": auth,
    }
    cfg = _validate({k: v for k, v in given.items() if v is not None})
    table_lines = ["[llm]"]
    for key in _CONFIG_KEYS:
        if cfg[key] is not None:
            table_lines.append(f"{key} = {_toml_value(cfg[key])}")

    path = Path(config_path)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    out = []
    replaced = False
    skipping = False
    for line in existing.splitlines():
        stripped = line.strip()
        if _LLM_HEADER_RE.match(stripped):
            skipping = True
            if not replaced:
                out.extend(table_lines)
                replaced = True
            continue
        if skipping and stripped.startswith("["):
            skipping = False
            out.append("")
        if not skipping:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.extend(table_lines)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Failure classification
# --------------------------------------------------------------------------

def _status_category(code):
    if code in (401, 403):
        return "auth"
    if code == 429:
        return "rate_limit"
    if code in (408, 504):
        return "timeout"
    return "network"


def _classify_exception(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return _status_category(exc.code)
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (socket.timeout, TimeoutError)):
        return "timeout"
    return "network"


def _body_says_key_invalid(exc):
    try:
        body = exc.read().decode("utf-8", "replace").lower()
    except Exception:
        return False
    return "api key not valid" in body or "api_key_invalid" in body


# --------------------------------------------------------------------------
# HTTP adapters
# --------------------------------------------------------------------------

def _http_call(url, headers, payload, timeout, extract, gemini=False):
    all_headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    all_headers.update(headers)
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=all_headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            raw = reply.read()
    except urllib.error.HTTPError as exc:
        category = _status_category(exc.code)
        if gemini and exc.code == 400 and _body_says_key_invalid(exc):
            category = "auth"
        return None, _error(category)
    except Exception as exc:
        return None, _error(_classify_exception(exc))
    try:
        text = extract(json.loads(raw))
    except Exception:
        return None, _error("network")
    if not isinstance(text, str) or not text:
        return None, _error("network")
    return text, None


def _key(resolved):
    name = resolved["api_key_env"]
    value = os.environ.get(name) if name else None
    return name, value


def _missing_key(name):
    return _error("auth", f"missing API key: environment variable {name} is not set")


def _user_messages(prompt):
    return [{"role": "user", "content": prompt}]


def _anthropic(prompt, resolved, params):
    name, key = _key(resolved)
    if not key:
        return None, _missing_key(name)
    payload = {
        "model": resolved["model"],
        "max_tokens": params.get("max_tokens", 32000),
        "messages": _user_messages(prompt),
    }
    if "temperature" in params:
        payload["temperature"] = params["temperature"]
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}

    def extract(data):
        return "".join(b["text"] for b in data["content"] if b.get("type") == "text")

    url = resolved["base_url"].rstrip("/") + "/v1/messages"
    return _http_call(url, headers, payload, resolved["timeout_seconds"], extract)


def _openai_extract(data):
    return data["choices"][0]["message"]["content"]


def _openai_payload(prompt, resolved, params, max_tokens_field):
    payload = {"model": resolved["model"], "messages": _user_messages(prompt)}
    if "max_tokens" in params:
        payload[max_tokens_field] = params["max_tokens"]
    if "temperature" in params:
        payload["temperature"] = params["temperature"]
    return payload


def _openai(prompt, resolved, params):
    name, key = _key(resolved)
    if not key:
        return None, _missing_key(name)
    payload = _openai_payload(prompt, resolved, params, "max_completion_tokens")
    url = resolved["base_url"].rstrip("/") + "/chat/completions"
    return _http_call(url, {"Authorization": f"Bearer {key}"}, payload,
                      resolved["timeout_seconds"], _openai_extract)


def _openai_compatible(prompt, resolved, params):
    _, key = _key(resolved)
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    payload = _openai_payload(prompt, resolved, params, "max_tokens")
    url = resolved["base_url"].rstrip("/") + "/chat/completions"
    return _http_call(url, headers, payload, resolved["timeout_seconds"], _openai_extract)


def _gemini(prompt, resolved, params):
    name, key = _key(resolved)
    if not key:
        return None, _missing_key(name)
    model = resolved["model"]
    if model.startswith("models/"):
        model = model[len("models/"):]
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    generation = {}
    if "max_tokens" in params:
        generation["maxOutputTokens"] = params["max_tokens"]
    if "temperature" in params:
        generation["temperature"] = params["temperature"]
    if generation:
        payload["generationConfig"] = generation

    def extract(data):
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))

    url = resolved["base_url"].rstrip("/") + f"/v1beta/models/{model}:generateContent"
    return _http_call(url, {"x-goog-api-key": key}, payload, resolved["timeout_seconds"],
                      extract, gemini=True)


def _ollama(prompt, resolved, params):
    _, key = _key(resolved)
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    options = {}
    if "max_tokens" in params:
        options["num_predict"] = params["max_tokens"]
    if "temperature" in params:
        options["temperature"] = params["temperature"]
    if "num_ctx" in params:
        options["num_ctx"] = params["num_ctx"]
    payload = {"model": resolved["model"], "messages": _user_messages(prompt), "stream": False}
    if options:
        payload["options"] = options

    def extract(data):
        return data["message"]["content"]

    url = resolved["base_url"].rstrip("/") + "/api/chat"
    return _http_call(url, headers, payload, resolved["timeout_seconds"], extract)


# --------------------------------------------------------------------------
# claude-cli adapter
# --------------------------------------------------------------------------

def _cli_category(text):
    text = text.lower()
    for category, markers in (
        ("rate_limit", ("rate limit", "rate_limit", "429")),
        ("auth", ("auth", "login", "api key", "401", "403")),
        ("timeout", ("timed out", "timeout")),
    ):
        if any(marker in text for marker in markers):
            return category
    return "network"


def _cli_failure(category, auth, flag):
    if category == "auth" and auth is None and flag == "--bare":
        return _error("auth", _BARE_AUTH_MESSAGE)
    return _error(category, f"claude command failed ({category})")


def _parse_stream(stdout):
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    events = []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            return None
        if not isinstance(event, dict):
            return None
        events.append(event)
    return events


def _claude_cli(prompt, resolved, params):
    auth = resolved["auth"]
    env = dict(os.environ)
    if auth == "login":
        flag = "--safe-mode"
        env.pop("ANTHROPIC_API_KEY", None)
    elif auth == "key":
        flag = "--bare"
    else:
        flag = "--bare" if os.environ.get("ANTHROPIC_API_KEY") else "--safe-mode"

    args = ["claude", "-p", "--model", resolved["model"], "--tools", "",
            "--output-format", "stream-json", "--verbose", flag]
    for name, value in params.items():
        args += ["--" + name.replace("_", "-"), str(value)]

    try:
        proc = subprocess.run(args, input=prompt, capture_output=True, text=True,
                              timeout=resolved["timeout_seconds"], env=env)
    except subprocess.TimeoutExpired:
        return None, _cli_failure("timeout", auth, flag)
    except OSError:
        return None, _cli_failure("network", auth, flag)

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    events = _parse_stream(stdout)
    if events is None:
        if proc.returncode == 0:
            return stdout, None
        return None, _cli_failure(_cli_category(stdout + "\n" + stderr), auth, flag)

    failed = [e for e in events if e.get("type") == "result" and e.get("is_error") is True]
    if failed or proc.returncode != 0:
        text = " ".join(str(e.get("result", "")) for e in failed) + "\n" + stderr
        return None, _cli_failure(_cli_category(text), auth, flag)

    parts = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        message = event.get("message") or {}
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    return "".join(parts), None


_ADAPTERS = {
    "claude-cli": _claude_cli,
    "anthropic": _anthropic,
    "openai": _openai,
    "openai-compatible": _openai_compatible,
    "gemini": _gemini,
    "ollama": _ollama,
}


# --------------------------------------------------------------------------
# complete()
# --------------------------------------------------------------------------

def _write_call_record(response):
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
    calls_dir = Path.cwd() / ".hotdocs" / "calls"
    calls_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex}.json"
    (calls_dir / filename).write_text(json.dumps(record), encoding="utf-8")


def complete(prompt, model, *, backend=None, **params):
    if backend is not None:
        name = getattr(backend, "__name__", None) or type(backend).__name__
        try:
            result = backend(prompt, model, **params)
        except Exception as exc:
            text, error, backend_name = None, _error(_classify_exception(exc)), name
        else:
            text = _get(result, "text")
            error = _get(result, "model_call_error")
            if error is not None:
                error = {"category": _get(error, "category"), "message": _get(error, "message")}
            backend_name = _get(result, "backend") or name
    else:
        try:
            config = load_config()
        except ValueError as exc:
            raise ModelResolutionError(str(exc)) from None
        resolved = resolve_provider(model, config)
        backend_name = resolved["provider"]
        text, error = _ADAPTERS[backend_name](prompt, resolved, params)

    response = {
        "text": text,
        "model": model,
        "backend": backend_name,
        "model_call_error": error,
    }
    _write_call_record(response)
    return response


# --------------------------------------------------------------------------
# Setup helpers
# --------------------------------------------------------------------------

def detect_providers(env=None, probe_ollama=True):
    env = os.environ if env is None else env
    entries = []
    for provider, info in PROVIDERS.items():
        key_env = info["default_api_key_env"]
        if provider == "claude-cli":
            available = shutil.which("claude", path=env.get("PATH", "")) is not None
            reason = "claude found on PATH" if available else "claude not found on PATH"
        elif provider == "openai-compatible":
            available = False
            reason = "needs a base_url"
        elif provider == "ollama":
            if probe_ollama:
                request = urllib.request.Request(info["default_base_url"] + "/api/tags",
                                                 headers={"User-Agent": USER_AGENT})
                try:
                    with urllib.request.urlopen(request, timeout=1):
                        pass
                    available = True
                except Exception:
                    available = False
                reason = "Ollama server answered" if available else "no Ollama server answering"
            else:
                available = False
                reason = "Ollama server not probed"
        else:
            available = bool((env.get(key_env) or "").strip())
            reason = f"{key_env} is set" if available else f"{key_env} is not set"
        entries.append({
            "provider": provider,
            "available": available,
            "reason": reason,
            "suggested_model": info["suggested_model"],
            "api_key_env": key_env,
        })
    return entries


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}")
    info = PROVIDERS[provider]
    if info["needs_base_url"] and not base_url:
        raise ValueError(f"provider {provider!r} requires a base_url")
    resolved = {
        "provider": provider,
        "model": model,
        "base_url": base_url or info["default_base_url"],
        "api_key_env": api_key_env or info["default_api_key_env"],
        "timeout_seconds": timeout_seconds,
        "auth": auth,
    }
    params = {} if provider == "claude-cli" else {"max_tokens": 1024}
    _, error = _ADAPTERS[provider]("Reply with the word OK.", resolved, params)
    return {"ok": error is None, "error": error}
