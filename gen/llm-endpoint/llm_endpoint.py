"""LLM Endpoint — vendor-agnostic transport for every model call this
pipeline makes.

Public entry point: `complete(prompt, model, *, backend=None, **params)`.

Providers (`PROVIDERS`): `claude-cli` (the `claude` command), `anthropic`,
`openai`, `openai-compatible`, `gemini`, and `ollama`; the last four
HTTP providers use only the standard library. A model string is
`<provider>:<model>` or a bare model name, resolved against an optional
`hotdocs.toml` (see `load_config`). Setup helpers for `hotdocs init`:
`PROVIDERS`, `load_config`, `save_config`, `detect_providers`,
`check_connection`.

See `specs/components/llm-endpoint/` for the normative requirements this
implementation satisfies (R-ENDPOINT-001 through R-ENDPOINT-009).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ModelResolutionError(Exception):
    """Raised when a model identifier resolves to no usable provider.

    This is a caller/configuration mistake (R-ENDPOINT-002), caught
    before any network call is attempted — never a `model_call_error`,
    and never a silent fallback to some other backend.
    """


# ---------------------------------------------------------------------------
# ModelResponse
# ---------------------------------------------------------------------------

_VALID_ERROR_CATEGORIES = {"network", "auth", "rate_limit", "timeout"}


def _make_response(
    *,
    text: Optional[str],
    model: str,
    backend: str,
    model_call_error: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build a `ModelResponse`-shaped dict.

    Exactly one of `text` / `model_call_error` is populated, never both
    and never neither.
    """
    if model_call_error is not None:
        category = model_call_error.get("category")
        if category not in _VALID_ERROR_CATEGORIES:
            raise ValueError(
                f"model_call_error.category must be one of "
                f"{sorted(_VALID_ERROR_CATEGORIES)}, got {category!r}"
            )
        text = None
    return {
        "text": text,
        "model": model,
        "backend": backend,
        "model_call_error": model_call_error,
    }


def _error_response(model: str, backend: str, category: str, message: str) -> Dict[str, Any]:
    return _make_response(
        text=None,
        model=model,
        backend=backend,
        model_call_error={"category": category, "message": message},
    )


# ---------------------------------------------------------------------------
# Providers (R-ENDPOINT-003)
# ---------------------------------------------------------------------------

# `suggested_model` is a hint for setup only, never a default `complete()`
# applies: the caller always names the model. An empty string means there
# is no sensible suggestion (an openai-compatible server serves whatever
# its operator loaded).
PROVIDERS: Dict[str, Dict[str, Any]] = {
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

# Providers whose API key is mandatory: a missing key is an `auth` error
# without a network call. openai-compatible and ollama send a key only if
# one is configured and present.
_KEY_REQUIRED = {"anthropic", "openai", "gemini"}

# D52/R-ENDPOINT-004: the floor for a completion call's bound is 300 s.
MIN_TIMEOUT_SECONDS = 300
DEFAULT_TIMEOUT_SECONDS = 600
ANTHROPIC_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS  # legacy name

# Non-streaming Messages API calls must send max_tokens; generation needs
# room for a whole component's code, thinking tokens included.
_ANTHROPIC_DEFAULT_MAX_TOKENS = 32000
_ANTHROPIC_VERSION = "2023-06-01"
_USER_AGENT = "hotdocs-llm-endpoint/1.0"

_CLAUDE_CLI = "claude"


# ---------------------------------------------------------------------------
# Model-string resolution (R-ENDPOINT-002) — pure, deterministic
# ---------------------------------------------------------------------------


def parse_model(model: Any) -> Tuple[Optional[str], Any]:
    """Split `<provider>:<model>`. The prefix counts only when it is a
    known provider name, so an Ollama tag such as `llama3.1:8b` is a bare
    model name while `ollama:llama3.1:8b` names the provider."""
    if isinstance(model, str) and ":" in model:
        prefix, rest = model.split(":", 1)
        if prefix in PROVIDERS:
            if not rest:
                raise ModelResolutionError(
                    f"model identifier {model!r} names provider {prefix!r} but no model"
                )
            return prefix, rest
    return None, model


def resolve_provider(model: Any, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve a model identifier to `{provider, model, base_url,
    api_key_env, timeout_seconds}`.

    Deterministic function of `model` and `config` only. Raises
    `ModelResolutionError` when no usable provider results — never a
    silent fallback.
    """
    if not isinstance(model, str) or not model:
        raise ModelResolutionError(f"no implemented backend for model identifier {model!r}")

    prefix, native = parse_model(model)
    if prefix is not None:
        provider = prefix
        cfg = config if (config and config["provider"] == provider) else None
    elif config:
        provider = config["provider"]
        native = model
        cfg = config
    elif model.startswith("claude-"):
        # Unconfigured legacy rule: a bare claude-* name uses the claude CLI.
        provider = "claude-cli"
        native = model
        cfg = None
    else:
        raise ModelResolutionError(
            f"no implemented backend for model identifier {model!r}"
        )

    meta = PROVIDERS[provider]
    base_url = (cfg or {}).get("base_url") or meta["default_base_url"]
    if meta["needs_base_url"] and not base_url:
        raise ModelResolutionError(
            f"provider {provider!r} needs a base_url (set [llm] base_url in hotdocs.toml)"
        )
    return {
        "provider": provider,
        "model": native,
        "base_url": base_url,
        "api_key_env": (cfg or {}).get("api_key_env") or meta["default_api_key_env"],
        "timeout_seconds": (cfg or {}).get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS,
    }


def resolve_backend_name(model: str) -> str:
    """Legacy single-argument resolver, kept for compatibility: returns
    the pre-multi-provider backend label, `"anthropic"`, for a bare
    `claude-*` identifier and raises `ModelResolutionError` otherwise.
    New code uses `resolve_provider`, whose `claude-cli` provider is what
    that label meant."""
    if isinstance(model, str) and model.startswith("claude-"):
        return "anthropic"
    raise ModelResolutionError(
        f"no implemented backend for model identifier {model!r}"
    )


# ---------------------------------------------------------------------------
# Configuration: hotdocs.toml (R-ENDPOINT-007)
# ---------------------------------------------------------------------------

CONFIG_ENV_VAR = "VAR_HOTDOCS_CONFIG"
CONFIG_FILENAME = "hotdocs.toml"

_LLM_KEYS = {"provider", "model", "base_url", "api_key_env", "timeout_seconds"}
_SECRETISH = ("key", "token", "secret", "password", "credential")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def _validate_llm(table: Any) -> Dict[str, Any]:
    """Validate an `[llm]` table and return the normalized dict, or raise
    ValueError naming the problem."""
    if not isinstance(table, dict):
        raise ValueError("[llm] must be a table")
    for key in table:
        if key not in _LLM_KEYS:
            if any(word in str(key).lower() for word in _SECRETISH):
                raise ValueError(
                    f"[llm] has a {key!r} entry: hotdocs.toml must never hold a "
                    f"secret; name the environment variable with api_key_env instead"
                )
            raise ValueError(f"[llm] has an unknown entry {key!r}")

    provider = table.get("provider")
    if provider not in PROVIDERS:
        raise ValueError(
            f"[llm] provider must be one of {sorted(PROVIDERS)}, got {provider!r}"
        )
    model = table.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("[llm] model must be a non-empty string")

    base_url = table.get("base_url") or None
    if base_url is not None:
        if not isinstance(base_url, str) or not re.match(r"^https?://\S+$", base_url):
            raise ValueError("[llm] base_url must be an http:// or https:// URL")
    api_key_env = table.get("api_key_env") or None
    if api_key_env is not None:
        if not isinstance(api_key_env, str) or not _ENV_NAME_RE.match(api_key_env):
            raise ValueError(
                "[llm] api_key_env must be the NAME of an environment variable "
                "(letters, digits, underscore), never the key itself"
            )
        if api_key_env not in os.environ and api_key_env in os.environ.values():
            raise ValueError(
                "[llm] api_key_env equals the value of an environment variable: "
                "it must be a variable name, never the key itself"
            )
    timeout = table.get("timeout_seconds")
    if timeout is not None:
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < MIN_TIMEOUT_SECONDS:
            raise ValueError(
                f"[llm] timeout_seconds must be an integer of at least {MIN_TIMEOUT_SECONDS}"
            )

    if provider == "claude-cli" and (base_url or api_key_env):
        raise ValueError("[llm] provider 'claude-cli' takes no base_url or api_key_env")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError(f"[llm] provider {provider!r} requires a base_url")
    return {
        "provider": provider,
        "model": model.strip(),
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout,
    }


def _discover_config_path() -> Optional[Path]:
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        path = Path(env_path)
        if not path.is_file():
            raise ValueError(f"{CONFIG_ENV_VAR} names a file that does not exist: {env_path}")
        return path
    local = Path.cwd() / CONFIG_FILENAME
    return local if local.is_file() else None


def load_config(config_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return the validated `[llm]` table of a hotdocs.toml, or None.

    With no `config_path`, discovery is: the file `VAR_HOTDOCS_CONFIG`
    names, then `hotdocs.toml` in the current directory. An explicit
    `config_path` that does not exist, or a file with no `[llm]` table,
    means no config (None). A config that exists but is invalid raises
    ValueError naming the problem.
    """
    path = Path(config_path) if config_path is not None else _discover_config_path()
    if path is None or not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path} is not valid TOML: {exc}") from None
    except OSError as exc:
        raise ValueError(f"{path} could not be read: {exc.strerror or 'OS error'}") from None
    if "llm" not in data:
        return None
    return _validate_llm(data["llm"])


def _render_llm_table(cfg: Dict[str, Any]) -> str:
    lines = ["[llm]", f"provider = {json.dumps(cfg['provider'])}", f"model = {json.dumps(cfg['model'])}"]
    if cfg["base_url"]:
        lines.append(f"base_url = {json.dumps(cfg['base_url'])}")
    if cfg["api_key_env"]:
        lines.append(f"api_key_env = {json.dumps(cfg['api_key_env'])}")
    if cfg["timeout_seconds"] is not None:
        lines.append(f"timeout_seconds = {int(cfg['timeout_seconds'])}")
    return "\n".join(lines) + "\n"


_TABLE_HEADER_RE = re.compile(r"^\s*\[")
_LLM_HEADER_RE = re.compile(r"^\s*\[llm\]\s*(#.*)?$")


def save_config(
    config_path: Path,
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    api_key_env: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
) -> None:
    """Validate and write the `[llm]` table of a hotdocs.toml.

    Any other content already in the file is kept; only the `[llm]` table
    is replaced (or appended). Refuses an unknown provider or anything
    that looks like a secret, and writes nothing in that case.
    """
    cfg = _validate_llm(
        {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "timeout_seconds": timeout_seconds,
        }
    )
    path = Path(config_path)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    kept: List[str] = []
    skipping = False
    for line in existing.splitlines():
        if _LLM_HEADER_RE.match(line):
            skipping = True
            continue
        if skipping and _TABLE_HEADER_RE.match(line):
            skipping = False
        if not skipping:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    new_text = ("\n".join(kept) + "\n\n" if kept else "") + _render_llm_table(cfg)

    parsed = tomllib.loads(new_text)  # never write a file that does not parse back
    _validate_llm(parsed["llm"])

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".hotdocs-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(new_text)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _load_config_for_complete() -> Optional[Dict[str, Any]]:
    try:
        return load_config()
    except ValueError as exc:
        raise ModelResolutionError(f"invalid hotdocs configuration: {exc}") from None


# ---------------------------------------------------------------------------
# claude-cli backend (R-ENDPOINT-003)
# ---------------------------------------------------------------------------


class ClaudeCliBackend:
    """Dispatches a completion via the `claude` CLI's non-interactive mode
    (D45/D46), authenticating via `VAR-ANTHROPIC-API-KEY`
    (`ANTHROPIC_API_KEY` in the process environment, D46) when configured,
    or whatever Pro/Max subscription login the CLI itself resolves
    otherwise (`D82`) — never read or forwarded by this component in any
    other way.
    """

    name = "claude-cli"

    def __init__(self, timeout_seconds: Optional[int] = None) -> None:
        self.timeout_seconds = timeout_seconds or ANTHROPIC_TIMEOUT_SECONDS

    def __call__(self, prompt: str, model: str, **params: Any) -> Dict[str, Any]:
        # R-ENDPOINT-003: --tools "" is unconditional, every call. The
        # isolation flag alongside it depends on which credential is
        # configured (`D82`) — `--bare` refuses any non-API-key
        # credential outright, so a caller with no API key (billing
        # against a Pro/Max login instead) needs `--safe-mode`, which
        # gives the same CLAUDE.md/hooks isolation without that refusal.
        # This component never pre-empts the call by checking for a
        # credential itself; whatever the CLI resolves determines the
        # outcome, classified the same way any other failure already is.
        isolation_flag = (
            "--bare" if os.environ.get("ANTHROPIC_API_KEY") else "--safe-mode"
        )
        cmd = [
            _CLAUDE_CLI,
            "--print",
            "--model",
            model,
            "--tools",
            "",
            isolation_flag,
        ]
        for key, value in params.items():
            if value is None:
                continue
            flag = "--" + str(key).replace("_", "-")
            cmd.extend([flag, str(value)])

        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return _error_response(
                model, self.name, "timeout", "backend call exceeded its bounded timeout"
            )
        except FileNotFoundError:
            return _error_response(
                model, self.name, "network", "backend CLI not found in this environment"
            )
        except OSError:
            return _error_response(
                model, self.name, "network", "failed to invoke backend CLI"
            )

        if completed.returncode != 0:
            return _make_response(
                text=None,
                model=model,
                backend=self.name,
                model_call_error=self._classify_failure(
                    completed.returncode, completed.stderr, completed.stdout
                ),
            )

        return _make_response(
            text=completed.stdout,
            model=model,
            backend=self.name,
            model_call_error=None,
        )

    @staticmethod
    def _classify_failure(
        returncode: int, stderr: Optional[str], stdout: Optional[str] = None
    ) -> Dict[str, str]:
        """Classify a non-zero CLI exit into one of the four
        `model_call_error` categories. Never includes raw vendor text or
        any credential material — a short, backend-agnostic description
        only.

        Checks both streams (`D82`): a missing/invalid credential under
        `--safe-mode` reports "Not logged in" on stdout, with stderr
        empty — a real gap found once `--safe-mode` became a real
        dispatch path, not just `--bare`'s stderr-only failure shapes.
        """
        lowered = ((stderr or "") + " " + (stdout or "")).lower()
        if "rate limit" in lowered or "429" in lowered or "too many requests" in lowered:
            return {
                "category": "rate_limit",
                "message": "backend reported a rate limit",
            }
        if (
            "unauthorized" in lowered
            or "401" in lowered
            or "forbidden" in lowered
            or "403" in lowered
            or "api key" in lowered
            or "authentic" in lowered
            or "not logged in" in lowered
            or "/login" in lowered
        ):
            return {
                "category": "auth",
                "message": "backend rejected credentials",
            }
        return {
            "category": "network",
            "message": f"backend call failed (exit code {returncode})",
        }


# Legacy name: the one backend before multi-provider support.
AnthropicBackend = ClaudeCliBackend


# ---------------------------------------------------------------------------
# HTTP providers (R-ENDPOINT-008)
# ---------------------------------------------------------------------------


def _classify_http(status: int, body: str, provider: str) -> Dict[str, str]:
    """Map a non-2xx status onto the four categories. Static messages
    only: never the vendor's body text, a header, or a credential."""
    if status in (401, 403):
        return {"category": "auth", "message": "backend rejected credentials"}
    if status == 400 and provider == "gemini" and "api key" in body.lower():
        # Gemini's generateContent reports an invalid key as 400.
        return {"category": "auth", "message": "backend rejected credentials"}
    if status == 429:
        return {"category": "rate_limit", "message": "backend reported a rate limit"}
    if status in (408, 504):
        return {"category": "timeout", "message": "backend call timed out"}
    return {"category": "network", "message": f"backend call failed (HTTP {status})"}


class _HttpBackend:
    """Shared plumbing for the HTTP providers. Subclasses build the
    request and read the reply; every failure comes back as a
    `model_call_error` response — nothing is raised, retried, or echoed."""

    name = ""

    def __init__(
        self,
        base_url: Optional[str],
        api_key_env: Optional[str],
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds or DEFAULT_TIMEOUT_SECONDS

    # -- subclass hooks ---------------------------------------------------
    def build(self, prompt: str, model: str, params: Dict[str, Any]) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
        raise NotImplementedError

    def extract(self, data: Any) -> Optional[str]:
        raise NotImplementedError

    # -- common -----------------------------------------------------------
    def _api_key(self) -> Optional[str]:
        if not self.api_key_env:
            return None
        return (os.environ.get(self.api_key_env) or "").strip() or None

    def __call__(self, prompt: str, model: str, **params: Any) -> Dict[str, Any]:
        api_key = self._api_key()
        if self.name in _KEY_REQUIRED and api_key is None:
            return _error_response(
                model, self.name, "auth",
                f"no API key found in environment variable {self.api_key_env}",
            )
        url, headers, body = self.build(prompt, model, params)
        headers = dict(headers)
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("User-Agent", _USER_AGENT)
        self.add_auth(headers, api_key)
        request = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as reply:
                raw = reply.read()
        except urllib.error.HTTPError as exc:
            try:
                err_body = exc.read(4096).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001 - classification only needs a best-effort body
                err_body = ""
            return _make_response(
                text=None, model=model, backend=self.name,
                model_call_error=_classify_http(exc.code, err_body, self.name),
            )
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                return _error_response(model, self.name, "timeout", "backend call exceeded its bounded timeout")
            return _error_response(model, self.name, "network", "backend could not be reached")
        except (socket.timeout, TimeoutError):
            return _error_response(model, self.name, "timeout", "backend call exceeded its bounded timeout")
        except OSError:
            return _error_response(model, self.name, "network", "backend could not be reached")

        try:
            text = self.extract(json.loads(raw))
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return _error_response(model, self.name, "network", "backend returned an unreadable response")
        if not text:
            return _error_response(model, self.name, "network", "backend returned no text")
        return _make_response(text=text, model=model, backend=self.name, model_call_error=None)

    def add_auth(self, headers: Dict[str, str], api_key: Optional[str]) -> None:
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"


class AnthropicApiBackend(_HttpBackend):
    """Messages API: POST {base}/v1/messages, `x-api-key` plus
    `anthropic-version`; `max_tokens` is required; the reply's `content`
    is a list of blocks and only `text` blocks carry the answer (thinking
    blocks may precede them)."""

    name = "anthropic"

    def add_auth(self, headers, api_key):
        if api_key:
            headers["x-api-key"] = api_key
        headers["anthropic-version"] = _ANTHROPIC_VERSION

    def build(self, prompt, model, params):
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": int(params.get("max_tokens") or _ANTHROPIC_DEFAULT_MAX_TOKENS),
            "messages": [{"role": "user", "content": prompt}],
        }
        if params.get("temperature") is not None:
            body["temperature"] = params["temperature"]
        return f"{self.base_url}/v1/messages", {}, body

    def extract(self, data):
        blocks = data["content"]
        return "".join(b["text"] for b in blocks if b.get("type") == "text")


class OpenAIBackend(_HttpBackend):
    """Chat Completions: POST {base}/chat/completions, bearer auth; the
    answer is `choices[0].message.content`. The official API takes
    `max_completion_tokens` (`max_tokens` is deprecated and rejected by
    o-series models); an openai-compatible server takes `max_tokens`."""

    name = "openai"
    token_param = "max_completion_tokens"

    def build(self, prompt, model, params):
        body: Dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        if params.get("max_tokens") is not None:
            body[self.token_param] = int(params["max_tokens"])
        if params.get("temperature") is not None:
            body["temperature"] = params["temperature"]
        return f"{self.base_url}/chat/completions", {}, body

    def extract(self, data):
        return data["choices"][0]["message"]["content"]


class OpenAICompatibleBackend(OpenAIBackend):
    name = "openai-compatible"
    token_param = "max_tokens"


class GeminiBackend(_HttpBackend):
    """generateContent: POST {base}/v1beta/models/{model}:generateContent,
    key in the `x-goog-api-key` header (never the URL, so it cannot
    surface in an error); the answer is the concatenated text parts of
    `candidates[0].content`."""

    name = "gemini"

    def add_auth(self, headers, api_key):
        if api_key:
            headers["x-goog-api-key"] = api_key

    def build(self, prompt, model, params):
        native = model[len("models/"):] if model.startswith("models/") else model
        body: Dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        generation: Dict[str, Any] = {}
        if params.get("max_tokens") is not None:
            generation["maxOutputTokens"] = int(params["max_tokens"])
        if params.get("temperature") is not None:
            generation["temperature"] = params["temperature"]
        if generation:
            body["generationConfig"] = generation
        url = f"{self.base_url}/v1beta/models/{urllib.parse.quote(native, safe='')}:generateContent"
        return url, {}, body

    def extract(self, data):
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p["text"] for p in parts if "text" in p and not p.get("thought"))


class OllamaBackend(_HttpBackend):
    """Ollama: POST {base}/api/chat with `stream` false; the answer is
    `message.content`. A key is sent only if one is configured."""

    name = "ollama"

    def build(self, prompt, model, params):
        body: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        options: Dict[str, Any] = {}
        if params.get("max_tokens") is not None:
            options["num_predict"] = int(params["max_tokens"])
        if params.get("temperature") is not None:
            options["temperature"] = params["temperature"]
        if params.get("num_ctx") is not None:
            options["num_ctx"] = int(params["num_ctx"])
        if options:
            body["options"] = options
        return f"{self.base_url}/api/chat", {}, body

    def extract(self, data):
        return data["message"]["content"]


_HTTP_BACKENDS = {
    "anthropic": AnthropicApiBackend,
    "openai": OpenAIBackend,
    "openai-compatible": OpenAICompatibleBackend,
    "gemini": GeminiBackend,
    "ollama": OllamaBackend,
}


def _instantiate_backend(resolved: Dict[str, Any]) -> Callable[..., Dict[str, Any]]:
    provider = resolved["provider"]
    if provider == "claude-cli":
        return ClaudeCliBackend(resolved["timeout_seconds"])
    if provider in _HTTP_BACKENDS:
        return _HTTP_BACKENDS[provider](
            resolved["base_url"], resolved["api_key_env"], resolved["timeout_seconds"]
        )
    raise ModelResolutionError(f"no implemented backend named {provider!r}")


# ---------------------------------------------------------------------------
# Setup helpers for `hotdocs init` (R-ENDPOINT-009)
# ---------------------------------------------------------------------------


def detect_providers(
    env: Optional[Dict[str, str]] = None, probe_ollama: bool = True
) -> List[Dict[str, Any]]:
    """One entry per provider: whether it looks usable right now.

    `env` defaults to the process environment; when given, it alone
    supplies the key variables and `PATH`, so a test needs no real
    environment. Ollama is probed with a ~1 s `GET /api/tags`.
    """
    explicit = env is not None
    environment: Dict[str, str] = dict(env) if explicit else dict(os.environ)
    found: List[Dict[str, Any]] = []
    for provider, meta in PROVIDERS.items():
        key_env = meta["default_api_key_env"]
        if provider == "claude-cli":
            path = shutil.which(_CLAUDE_CLI, path=environment.get("PATH", "") if explicit else None)
            available = path is not None
            reason = "`claude` found on PATH" if available else "`claude` not found on PATH"
        elif provider == "openai-compatible":
            available = False
            reason = "needs a base_url and is not auto-detectable; configure it explicitly"
        elif provider == "ollama":
            if probe_ollama:
                available = _ollama_answers(meta["default_base_url"])
                reason = (
                    f"server answered at {meta['default_base_url']}"
                    if available else f"no server answered at {meta['default_base_url']}"
                )
            else:
                available = False
                reason = "not probed"
        else:
            available = bool((environment.get(key_env) or "").strip())
            reason = f"{key_env} is set" if available else f"{key_env} is not set"
        found.append(
            {
                "provider": provider,
                "available": available,
                "reason": reason,
                "suggested_model": meta["suggested_model"],
                "api_key_env": key_env,
            }
        )
    return found


def _ollama_answers(base_url: str) -> bool:
    try:
        request = urllib.request.Request(
            base_url.rstrip("/") + "/api/tags", headers={"User-Agent": _USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=1):
            return True
    except Exception:  # noqa: BLE001 - any failure means "not available"
        return False


def check_connection(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    api_key_env: Optional[str] = None,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """Make one tiny real completion and report `{ok, error}`.

    The probe's own bound (`timeout_seconds`) is deliberately short and
    is not subject to the 300-second floor of a real completion. It is
    not written to the call log. An unknown provider, or
    `openai-compatible` with no `base_url`, is a programming error and
    raises ValueError.
    """
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}; expected one of {sorted(PROVIDERS)}")
    meta = PROVIDERS[provider]
    url = base_url or meta["default_base_url"]
    if meta["needs_base_url"] and not url:
        raise ValueError(f"provider {provider!r} requires a base_url")
    key_env = api_key_env or meta["default_api_key_env"]
    if provider == "claude-cli":
        backend: Callable[..., Dict[str, Any]] = ClaudeCliBackend(timeout_seconds)
        params: Dict[str, Any] = {}
    else:
        backend = _HTTP_BACKENDS[provider](url, key_env, timeout_seconds)
        params = {"max_tokens": 1024}
    response = backend("Reply with the single word: ok", model, **params)
    error = response.get("model_call_error")
    if error is not None:
        return {"ok": False, "error": error}
    return {"ok": True, "error": None}


# ---------------------------------------------------------------------------
# Call log (R-ENDPOINT-006) — local-only, non-gating
# ---------------------------------------------------------------------------

_CALL_LOG_DIR = Path(".hotdocs") / "calls"


def _write_call_log(record: Dict[str, Any]) -> None:
    try:
        _CALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{record['timestamp'].replace(':', '').replace('.', '')}-{uuid.uuid4().hex}.json"
        (_CALL_LOG_DIR / filename).write_text(json.dumps(record) + "\n")
    except OSError:
        # The call log is a local, non-gating side effect
        # (constraints.md) — a failure to write it must never surface
        # as, or mask, the actual completion result.
        pass


def _log_record_for(model: str, response: Dict[str, Any]) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "backend": response.get("backend"),
    }
    error = response.get("model_call_error")
    if error is not None:
        record["model_call_error"] = error
    else:
        record["text_present"] = response.get("text") is not None
    return record


# ---------------------------------------------------------------------------
# Public entry point (R-ENDPOINT-001)
# ---------------------------------------------------------------------------


def complete(
    prompt: str,
    model: str,
    *,
    backend: Optional[Callable[..., Dict[str, Any]]] = None,
    **params: Any,
) -> Dict[str, Any]:
    """Send `prompt` to `model` and return a `ModelResponse` dict.

    `model` is a required, caller-supplied identifier — never hardcoded
    to a canonical pin, never defaulted to a specific vendor
    (R-ENDPOINT-001). It is `<provider>:<model>` or a bare name resolved
    against the optional hotdocs.toml (R-ENDPOINT-002); the response's
    `model` is the string the caller passed.

    `backend`, when omitted, is resolved internally from `model`
    (R-ENDPOINT-002/003). A caller supplying `backend` bypasses
    resolution entirely — for testing this component's own
    dispatch/classification/logging logic against an injected mock,
    never a real network call.

    `backend`, if supplied, MUST be a callable
    `backend(prompt, model, **params) -> ModelResponse`-shaped dict.

    `**params` is forwarded to the resolved/injected backend; the HTTP
    providers understand `max_tokens` and `temperature` (and Ollama
    `num_ctx`) and ignore the rest, the claude CLI turns each into a flag.
    """
    if backend is None:
        resolved = resolve_provider(model, _load_config_for_complete())
        backend_callable = _instantiate_backend(resolved)
        response = backend_callable(prompt, resolved["model"], **params)
        response["model"] = model
    else:
        response = backend(prompt, model, **params)

    _write_call_log(_log_record_for(model, response))

    return response
