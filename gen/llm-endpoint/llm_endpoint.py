"""LLM Endpoint — vendor-agnostic transport for every model call this
pipeline makes.

Public entry point: `complete(prompt, model, *, backend=None, **params)`.

See `specs/requirements/llm-endpoint/` for the normative requirements
this implementation satisfies (R-ENDPOINT-001 through R-ENDPOINT-006).
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ModelResolutionError(Exception):
    """Raised when a model identifier resolves to no implemented backend.

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


# ---------------------------------------------------------------------------
# Backend resolution (R-ENDPOINT-002) — pure, deterministic
# ---------------------------------------------------------------------------


def resolve_backend_name(model: str) -> str:
    """Resolve a model identifier to a backend name.

    Deterministic function of `model` only. Raises `ModelResolutionError`
    if no implemented backend matches — never a silent fallback.
    """
    if isinstance(model, str) and model.startswith("claude-"):
        return "anthropic"
    raise ModelResolutionError(
        f"no implemented backend for model identifier {model!r}"
    )


def _instantiate_backend(backend_name: str) -> Callable[..., Dict[str, Any]]:
    if backend_name == "anthropic":
        return AnthropicBackend()
    # Unreachable in v1 (resolve_backend_name only ever returns "anthropic"
    # or raises), kept explicit for when R-ENDPOINT-003 grows a second
    # backend behind this same split.
    raise ModelResolutionError(
        f"no implemented backend named {backend_name!r}"
    )


# ---------------------------------------------------------------------------
# Anthropic backend (R-ENDPOINT-003) — v1's one backend
# ---------------------------------------------------------------------------

# D52: floor is 300 seconds. Other backends/future tuning MAY raise this,
# never lower it.
ANTHROPIC_TIMEOUT_SECONDS = 300

_CLAUDE_CLI = "claude"


class AnthropicBackend:
    """Dispatches a completion via the `claude` CLI's non-interactive mode
    (D45/D46), authenticating via `VAR-ANTHROPIC-API-KEY`
    (`ANTHROPIC_API_KEY` in the process environment, D46) — never read or
    forwarded by this component in any other way.
    """

    name = "anthropic"

    def __call__(self, prompt: str, model: str, **params: Any) -> Dict[str, Any]:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            # Caught here rather than left to the CLI so the failure is
            # classified cleanly as `auth`, without ever naming or echoing
            # the (absent) credential itself.
            return _make_response(
                text=None,
                model=model,
                backend=self.name,
                model_call_error={
                    "category": "auth",
                    "message": "no credential configured for this backend",
                },
            )

        # R-ENDPOINT-003 / D53: --tools "" and --bare, every call,
        # unconditionally — structural isolation, not a system-prompt
        # convention. --print selects non-interactive mode.
        cmd = [
            _CLAUDE_CLI,
            "--print",
            "--model",
            model,
            "--tools",
            "",
            "--bare",
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
                timeout=ANTHROPIC_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return _make_response(
                text=None,
                model=model,
                backend=self.name,
                model_call_error={
                    "category": "timeout",
                    "message": "backend call exceeded its bounded timeout",
                },
            )
        except FileNotFoundError:
            return _make_response(
                text=None,
                model=model,
                backend=self.name,
                model_call_error={
                    "category": "network",
                    "message": "backend CLI not found in this environment",
                },
            )
        except OSError:
            return _make_response(
                text=None,
                model=model,
                backend=self.name,
                model_call_error={
                    "category": "network",
                    "message": "failed to invoke backend CLI",
                },
            )

        if completed.returncode != 0:
            return _make_response(
                text=None,
                model=model,
                backend=self.name,
                model_call_error=self._classify_failure(
                    completed.returncode, completed.stderr
                ),
            )

        return _make_response(
            text=completed.stdout,
            model=model,
            backend=self.name,
            model_call_error=None,
        )

    @staticmethod
    def _classify_failure(returncode: int, stderr: Optional[str]) -> Dict[str, str]:
        """Classify a non-zero CLI exit into one of the four
        `model_call_error` categories. Never includes raw vendor text or
        any credential material — a short, backend-agnostic description
        only.
        """
        lowered = (stderr or "").lower()
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
        ):
            return {
                "category": "auth",
                "message": "backend rejected credentials",
            }
        return {
            "category": "network",
            "message": f"backend call failed (exit code {returncode})",
        }


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
    (R-ENDPOINT-001).

    `backend`, when omitted, is resolved internally from `model`
    (R-ENDPOINT-002/003). A caller supplying `backend` bypasses
    resolution entirely — for testing this component's own
    dispatch/classification/logging logic against an injected mock,
    never a real network call.

    `backend`, if supplied, MUST be a callable
    `backend(prompt, model, **params) -> ModelResponse`-shaped dict.

    `**params` is forwarded verbatim to the resolved/injected backend;
    this component neither interprets nor validates it.
    """
    if backend is None:
        backend_name = resolve_backend_name(model)
        backend_callable = _instantiate_backend(backend_name)
    else:
        backend_callable = backend

    response = backend_callable(prompt, model, **params)

    _write_call_log(_log_record_for(model, response))

    return response
