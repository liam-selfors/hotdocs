"""Vendor-agnostic transport for every model call the pipeline makes."""

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

_ENTRIES = ("provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth")
_SECRET_NAME = re.compile(r"key|token|password|passwd|secret|credential")
_VAR_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_URL = re.compile(r"^https?://\S+$")

_MESSAGES = {
    "auth": "provider rejected the credentials",
    "rate_limit": "provider rate limit reached",
    "timeout": "provider call timed out",
    "network": "provider call failed",
}

_CLI_MARKERS = (
    ("rate_limit", ("rate limit", "rate_limit", "429")),
    ("auth", ("auth", "login", "api key", "401", "403")),
    ("timeout", ("timed out", "timeout")),
)

_CLI_BARE_AUTH_MESSAGE = (
    "claude command failed (auth): ANTHROPIC_API_KEY is set, so claude used it "
    "instead of your claude.ai login; unset it, or set auth = \"login\" in "
    "hotdocs.toml's [llm] table"
)


class ModelResolutionError(Exception):
    """A model identifier resolves to no usable provider."""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _error(category, message=None):
    return {"category": category, "message": message or _MESSAGES[category]}


# ---------------------------------------------------------------- config


def _validate_table(table):
    if not isinstance(table, dict):
        raise ValueError("hotdocs.toml's [llm] must be a table")
    for name in table:
        if name not in _ENTRIES:
            if _SECRET_NAME.search(str(name).lower()):
                raise ValueError(
                    f"hotdocs.toml [llm] entry {name!r} looks like a secret; "
                    "hotdocs.toml must never hold a secret: name the environment "
                    "variable in api_key_env instead"
                )
            raise ValueError(f"unknown entry {name!r} in hotdocs.toml's [llm] table")
    provider = table.get("provider")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError(
            f"[llm] provider must be one of {', '.join(PROVIDERS)}, not {provider!r}"
        )
    model = table.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("[llm] model is required and must be a non-empty string")
    base_url = table.get("base_url")
    if base_url == "":
        base_url = None
    if base_url is not None and not (isinstance(base_url, str) and _URL.match(base_url)):
        raise ValueError("[llm] base_url must be an http(s) URL")
    if provider == "claude-cli" and base_url is not None:
        raise ValueError("[llm] claude-cli takes no base_url")
    if PROVIDERS[provider]["needs_base_url"] and base_url is None:
        raise ValueError(f"[llm] {provider} requires a base_url")
    api_key_env = table.get("api_key_env")
    if api_key_env == "":
        api_key_env = None
    if api_key_env is not None:
        if not (isinstance(api_key_env, str) and _VAR_NAME.match(api_key_env)):
            raise ValueError(
                "[llm] api_key_env must be the NAME of an environment variable, "
                "never the key itself"
            )
        if api_key_env in os.environ.values():
            raise ValueError(
                "[llm] api_key_env looks like a pasted key; it must be the name of "
                "an environment variable, never the key itself"
            )
        if provider == "claude-cli":
            raise ValueError("[llm] claude-cli takes no api_key_env")
    timeout_seconds = table.get("timeout_seconds")
    if timeout_seconds is not None and not (
        isinstance(timeout_seconds, int)
        and not isinstance(timeout_seconds, bool)
        and timeout_seconds >= MIN_TIMEOUT_SECONDS
    ):
        raise ValueError(
            f"[llm] timeout_seconds must be an integer of at least {MIN_TIMEOUT_SECONDS}"
        )
    auth = table.get("auth")
    if auth is not None:
        if provider != "claude-cli":
            raise ValueError("[llm] auth is taken only by claude-cli")
        if auth not in ("login", "key"):
            raise ValueError('[llm] auth must be "login" or "key"')
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
        "auth": auth,
    }


def load_config(config_path=None):
    if config_path is None:
        env_path = os.environ.get("VAR_HOTDOCS_CONFIG")
        if env_path:
            config_path = Path(env_path)
            if not config_path.is_file():
                raise ValueError(f"VAR_HOTDOCS_CONFIG names {env_path}, which does not exist")
        else:
            config_path = Path.cwd() / "hotdocs.toml"
    config_path = Path(config_path)
    if not config_path.is_file():
        return None
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        raise ValueError(f"{config_path} is not valid TOML") from None
    if "llm" not in data:
        return None
    return _validate_table(data["llm"])


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    values = {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
        "auth": auth,
    }
    table = _validate_table({k: v for k, v in values.items() if v is not None})
    config_path = Path(config_path)
    existing = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    kept = []
    skipping = False
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            skipping = re.match(r"^\[\s*llm\s*\]", stripped) is not None
        if not skipping:
            kept.append(line)
    text = "\n".join(kept).rstrip("\n")
    if text:
        text += "\n\n"
    text += "[llm]\n"
    for name in _ENTRIES:
        value = table[name]
        if value is None:
            continue
        rendered = str(value) if name == "timeout_seconds" else json.dumps(value)
        text += f"{name} = {rendered}\n"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- resolution


def parse_model(model):
    prefix, sep, rest = model.partition(":")
    if sep and prefix in PROVIDERS:
        if not rest:
            raise ModelResolutionError(
                f"model identifier {model!r} names provider {prefix!r} but no model"
            )
        return prefix, rest
    return None, model


def resolve_provider(model, config=None):
    if config is not None:
        try:
            config = _validate_table({k: v for k, v in config.items() if v is not None})
        except ValueError as exc:
            raise ModelResolutionError(f"invalid hotdocs.toml: {exc}") from None
    provider, name = parse_model(model)
    if provider is None:
        if config is not None:
            provider = config["provider"]
        elif name.startswith("claude-"):
            provider = "claude-cli"
        else:
            raise ModelResolutionError(
                f"model {model!r} has no provider prefix and no hotdocs.toml configures one"
            )
    settings = config if config is not None and config["provider"] == provider else {}
    defaults = PROVIDERS[provider]
    resolved = {
        "provider": provider,
        "model": name,
        "base_url": settings.get("base_url") or defaults["default_base_url"],
        "api_key_env": settings.get("api_key_env") or defaults["default_api_key_env"],
        "timeout_seconds": settings.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS,
        "auth": settings.get("auth"),
    }
    if resolved["base_url"] is None and defaults["needs_base_url"]:
        raise ModelResolutionError(f"provider {provider!r} requires a base_url in hotdocs.toml")
    return resolved


def resolve_backend_name(model):
    provider, name = parse_model(model)
    if provider is None and name.startswith("claude-"):
        return "anthropic"
    return resolve_provider(model)["provider"]


# ---------------------------------------------------------------- HTTP


def _classify(exc, gemini=False):
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        if code in (401, 403):
            return "auth"
        if code == 429:
            return "rate_limit"
        if code in (408, 504):
            return "timeout"
        if gemini and code == 400:
            body = exc.read().decode("utf-8", "replace").lower()
            if "api key not valid" in body:
                return "auth"
        return "network"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, urllib.error.URLError) and isinstance(
        exc.reason, (socket.timeout, TimeoutError)
    ):
        return "timeout"
    return "network"


def _http_call(url, headers, payload, timeout, extract, gemini=False):
    all_headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    all_headers.update(headers)
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=all_headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            raw = reply.read()
    except OSError as exc:
        return None, _error(_classify(exc, gemini))
    try:
        text = extract(json.loads(raw))
    except Exception:
        return None, _error("network", "provider reply was unreadable")
    if not isinstance(text, str) or not text:
        return None, _error("network", "provider reply had no text")
    return text, None


def _key(resolved):
    name = resolved.get("api_key_env")
    return name, (os.environ.get(name) if name else None)


def _missing_key(name):
    return None, _error("auth", f"no API key: environment variable {name} is not set")


def _base(resolved):
    return resolved["base_url"].rstrip("/")


def _anthropic(prompt, resolved, params):
    name, key = _key(resolved)
    if not key:
        return _missing_key(name)
    payload = {
        "model": resolved["model"],
        "max_tokens": params.get("max_tokens", 32000),
        "messages": [{"role": "user", "content": prompt}],
    }
    if "temperature" in params:
        payload["temperature"] = params["temperature"]
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}

    def extract(data):
        return "".join(b["text"] for b in data["content"] if b.get("type") == "text")

    return _http_call(f"{_base(resolved)}/v1/messages", headers, payload,
                      resolved["timeout_seconds"], extract)


def _chat_extract(data):
    return data["choices"][0]["message"]["content"]


def _openai_payload(prompt, resolved, params, max_field):
    payload = {"model": resolved["model"], "messages": [{"role": "user", "content": prompt}]}
    if "max_tokens" in params:
        payload[max_field] = params["max_tokens"]
    if "temperature" in params:
        payload["temperature"] = params["temperature"]
    return payload


def _openai(prompt, resolved, params):
    name, key = _key(resolved)
    if not key:
        return _missing_key(name)
    payload = _openai_payload(prompt, resolved, params, "max_completion_tokens")
    return _http_call(f"{_base(resolved)}/chat/completions",
                      {"Authorization": f"Bearer {key}"}, payload,
                      resolved["timeout_seconds"], _chat_extract)


def _openai_compatible(prompt, resolved, params):
    _, key = _key(resolved)
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    payload = _openai_payload(prompt, resolved, params, "max_tokens")
    return _http_call(f"{_base(resolved)}/chat/completions", headers, payload,
                      resolved["timeout_seconds"], _chat_extract)


def _gemini(prompt, resolved, params):
    name, key = _key(resolved)
    if not key:
        return _missing_key(name)
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

    return _http_call(f"{_base(resolved)}/v1beta/models/{model}:generateContent",
                      {"x-goog-api-key": key}, payload,
                      resolved["timeout_seconds"], extract, gemini=True)


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
    payload = {
        "model": resolved["model"],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if options:
        payload["options"] = options
    return _http_call(f"{_base(resolved)}/api/chat", headers, payload,
                      resolved["timeout_seconds"], lambda d: d["message"]["content"])


# ---------------------------------------------------------------- claude-cli


def _cli_failure(text, auth, flag):
    lowered = text.lower()
    category = "network"
    for candidate, markers in _CLI_MARKERS:
        if any(marker in lowered for marker in markers):
            category = candidate
            break
    if category == "auth" and auth is None and flag == "--bare":
        return None, _error("auth", _CLI_BARE_AUTH_MESSAGE)
    return None, _error(category, f"claude command failed ({category})")


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
    auth = resolved.get("auth")
    env = dict(os.environ)
    if auth == "login":
        flag = "--safe-mode"
        env.pop("ANTHROPIC_API_KEY", None)
    elif auth == "key":
        flag = "--bare"
    else:
        flag = "--bare" if env.get("ANTHROPIC_API_KEY") else "--safe-mode"
    command = [
        "claude", "-p", "--model", resolved["model"], "--tools", "",
        "--output-format", "stream-json", "--verbose", flag,
    ]
    for name, value in params.items():
        command += ["--" + name.replace("_", "-"), str(value)]
    try:
        run = subprocess.run(command, input=prompt, capture_output=True, text=True,
                             timeout=resolved["timeout_seconds"], env=env)
    except subprocess.TimeoutExpired:
        return None, _error("timeout", "claude command failed (timeout)")
    except OSError:
        return _cli_failure("", auth, flag)
    stdout = run.stdout or ""
    stderr = run.stderr or ""
    events = _parse_stream(stdout)
    if events is None:
        if run.returncode == 0:
            return stdout, None
        return _cli_failure(stdout + "\n" + stderr, auth, flag)
    texts = []
    failures = []
    for event in events:
        if event.get("type") == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
        elif event.get("type") == "result" and event.get("is_error") is True:
            failures.append(str(event.get("result", "")))
    if failures or run.returncode != 0:
        return _cli_failure("\n".join(failures) + "\n" + stderr, auth, flag)
    return "".join(texts), None


_ADAPTERS = {
    "claude-cli": _claude_cli,
    "anthropic": _anthropic,
    "openai": _openai,
    "openai-compatible": _openai_compatible,
    "gemini": _gemini,
    "ollama": _ollama,
}


# ---------------------------------------------------------------- complete


def _write_call_log(record):
    directory = Path.cwd() / ".hotdocs" / "calls"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9A-Za-z]", "", record["timestamp"])
    path = directory / f"{stamp}-{uuid.uuid4().hex}.json"
    path.write_text(json.dumps(record), encoding="utf-8")


def complete(prompt, model, *, backend=None, **params):
    if backend is not None:
        backend_name = getattr(backend, "__name__", type(backend).__name__)
        try:
            reply = backend(prompt, model, **params)
        except Exception as exc:
            text, error = None, _error(_classify(exc))
        else:
            backend_name = _get(reply, "backend") or backend_name
            raw_error = _get(reply, "model_call_error")
            if raw_error is not None:
                text = None
                error = {
                    "category": _get(raw_error, "category"),
                    "message": _get(raw_error, "message"),
                }
            else:
                text, error = _get(reply, "text"), None
    else:
        try:
            config = load_config()
        except ValueError as exc:
            raise ModelResolutionError(f"invalid hotdocs.toml: {exc}") from None
        resolved = resolve_provider(model, config)
        backend_name = resolved["provider"]
        text, error = _ADAPTERS[backend_name](prompt, resolved, params)
    response = {
        "text": text,
        "model": model,
        "backend": backend_name,
        "model_call_error": error,
    }
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "backend": backend_name,
    }
    if error is None:
        record["text_present"] = text is not None
    else:
        record["model_call_error"] = error
    _write_call_log(record)
    return response


# ---------------------------------------------------------------- setup helpers


def detect_providers(env=None, probe_ollama=True):
    if env is None:
        env = os.environ
    results = []
    for provider, info in PROVIDERS.items():
        key_env = info["default_api_key_env"]
        if provider == "claude-cli":
            path = env.get("PATH") or ""
            available = bool(path) and shutil.which("claude", path=path) is not None
            reason = "claude command found on PATH" if available else "claude command not found on PATH"
        elif provider == "openai-compatible":
            available = False
            reason = "needs a base_url"
        elif provider == "ollama":
            available = False
            reason = "Ollama server not probed"
            if probe_ollama:
                request = urllib.request.Request(
                    info["default_base_url"] + "/api/tags", headers={"User-Agent": USER_AGENT}
                )
                try:
                    with urllib.request.urlopen(request, timeout=1):
                        pass
                    available = True
                    reason = "Ollama server answered"
                except OSError:
                    reason = "no Ollama server answered"
        else:
            available = bool((env.get(key_env) or "").strip())
            reason = f"{key_env} is set" if available else f"{key_env} is not set"
        results.append({
            "provider": provider,
            "available": available,
            "reason": reason,
            "suggested_model": info["suggested_model"],
            "api_key_env": key_env,
        })
    return results


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}")
    info = PROVIDERS[provider]
    base_url = base_url or info["default_base_url"]
    if info["needs_base_url"] and not base_url:
        raise ValueError(f"provider {provider!r} requires a base_url")
    resolved = {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env or info["default_api_key_env"],
        "timeout_seconds": timeout_seconds,
        "auth": auth,
    }
    params = {} if provider == "claude-cli" else {"max_tokens": 1024}
    _, error = _ADAPTERS[provider]("Reply with the single word OK.", resolved, params)
    return {"ok": error is None, "error": error}
