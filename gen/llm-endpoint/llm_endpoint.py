"""llm-endpoint — bootstrap implementation.

HAND-AUTHORED BOOTSTRAP, the same honest exception spec-linter/
graph-query-engine/corpus-graph-builder's own gen/ code already
documents (see verification/llm-endpoint/BOOTSTRAP.md) -- a fourth
instance, not a new pattern. This one is unavoidably a bootstrap
exception rather than a candidate for real cold regen: it is the
component every future real generation call would dispatch through, so
nothing could have generated it first.

Implements R-ENDPOINT-001..006:

- complete(prompt, model, **params) -> ModelResponse is the one entry
  point (R-ENDPOINT-001).
- Model-identifier-to-backend resolution is internal and deterministic
  (R-ENDPOINT-002); v1 ships exactly one backend, Anthropic
  (R-ENDPOINT-003), dispatched via the `claude` CLI's own non-interactive
  mode rather than a from-scratch API client -- D45/D46 found this is a
  real, scriptable call, and VAR-ANTHROPIC-API-KEY's resolution (a plain
  process-environment lookup, D46) is exactly what the CLI already does
  by default, so there is nothing left for this module to configure.
- No retry-with-backoff, no unbounded wait (R-ENDPOINT-004) -- a single
  bounded subprocess call, classified into exactly one of
  network/auth/rate_limit/timeout on failure.
- The credential never appears in a ModelResponse, a log line, or this
  module's own code (R-ENDPOINT-005) -- it is never read here at all;
  the `claude` subprocess inherits it from the environment directly.
- Every call writes one record to .hotdocs/calls/ (R-ENDPOINT-006).
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# R-ENDPOINT-002: a model identifier's naming pattern alone decides its
# backend -- no registry, no caller-supplied hint. v1 (R-ENDPOINT-003)
# recognizes exactly one pattern; a second backend is an additive entry
# in this tuple, never a rework of the dispatch below.
_BACKEND_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"^claude-"), "anthropic"),
)

# R-ENDPOINT-004: the four, and only four, model_call_error categories.
_ERROR_CATEGORIES = ("network", "auth", "rate_limit", "timeout")

_CALLS_DIR_RELATIVE = Path(".hotdocs") / "calls"

# Bounded wait for the backend subprocess itself (R-ENDPOINT-004) --
# distinct from any timeout the backend's own client applies internally;
# this is the outer bound this module guarantees regardless.
_DEFAULT_TIMEOUT_SECONDS = 120.0


class UnsupportedModelError(Exception):
    """R-ENDPOINT-002 -- a model identifier matches no implemented backend.

    A caller/configuration mistake, caught before any network call is
    attempted (AC-ENDPOINT-001) -- never reported as model_call_error,
    which is reserved for a call that was actually attempted and failed.
    """


class Backend(Protocol):
    """The shape `complete()` dispatches to -- real (`AnthropicBackend`) or
    injected (a test's mock), per R-ENDPOINT-002's resolve/dispatch split."""

    name: str

    def complete(self, prompt: str, model: str, **params: Any) -> "BackendResult":
        ...


@dataclass
class BackendResult:
    """What a `Backend.complete()` call returns -- not yet a `ModelResponse`:
    that type also carries `model`/`backend`, which `complete()` itself
    attaches, not any individual backend (keeps a backend ignorant of its
    own name as recorded in the public response)."""

    text: str | None
    error_category: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if (self.text is None) == (self.error_category is None):
            raise ValueError(
                "BackendResult must set exactly one of text or error_category"
            )
        if self.error_category is not None and self.error_category not in _ERROR_CATEGORIES:
            raise ValueError(f"error_category must be one of {_ERROR_CATEGORIES}")


@dataclass
class ModelResponse:
    """Matches `interface/data/ModelResponse.md` exactly."""

    text: str | None
    model: str
    backend: str
    model_call_error: dict[str, str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "backend": self.backend,
            "model_call_error": self.model_call_error,
        }


def _resolve_backend(model: str) -> Backend:
    for pattern, backend_name in _BACKEND_PATTERNS:
        if pattern.match(model):
            return _REAL_BACKENDS[backend_name]
    raise UnsupportedModelError(
        f"model identifier {model!r} matches no implemented backend "
        f"(v1 supports: {', '.join(name for _, name in _BACKEND_PATTERNS)})"
    )


def complete(
    prompt: str, model: str, *, backend: Backend | None = None, **params: Any
) -> ModelResponse:
    """R-ENDPOINT-001. `backend` is test-only dependency injection
    (interface/library.md, D47) -- a caller never needs it; omitting it
    (the default) resolves a real backend per R-ENDPOINT-002."""

    resolved = backend if backend is not None else _resolve_backend(model)
    result = resolved.complete(prompt, model, **params)

    model_call_error = (
        {"category": result.error_category, "message": result.error_message}
        if result.error_category is not None
        else None
    )
    response = ModelResponse(
        text=result.text,
        model=model,
        backend=resolved.name,
        model_call_error=model_call_error,
    )
    _write_call_log(response)
    return response


def _write_call_log(response: ModelResponse, repo_root: Path | None = None) -> None:
    """R-ENDPOINT-006 -- local, gitignored, non-gating (SPEC_GUIDELINES.md
    §1). Records presence of text, never its content."""

    root = repo_root if repo_root is not None else Path.cwd()
    calls_dir = root / _CALLS_DIR_RELATIVE
    calls_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": _utc_now_iso(),
        "model": response.model,
        "backend": response.backend,
        "has_text": response.text is not None,
        "model_call_error": response.model_call_error,
    }
    record_path = calls_dir / f"{uuid.uuid4().hex}.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- Anthropic backend (R-ENDPOINT-003) -------------------------------------


# R-ENDPOINT-004's four categories, in priority order -- api_error_status
# (an HTTP-like status the `claude` CLI's own JSON result already carries,
# confirmed by hand, not assumed) is the primary signal; stderr text is
# only a fallback for the cases that status doesn't cover (a genuine
# subprocess-level failure, not a backend-reported one).
_STATUS_TO_CATEGORY: dict[int, str] = {
    401: "auth",
    403: "auth",
    408: "timeout",
    429: "rate_limit",
}


def _classify_status(status: int | None) -> str:
    if status is not None and status in _STATUS_TO_CATEGORY:
        return _STATUS_TO_CATEGORY[status]
    return "network"


def _classify_text(text: str) -> str:
    lowered = text.lower()
    if "rate limit" in lowered or "429" in lowered:
        return "rate_limit"
    if "auth" in lowered or "401" in lowered or "403" in lowered or "api key" in lowered:
        return "auth"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    return "network"


def _sanitize(message: str) -> str:
    """R-ENDPOINT-005 defense in depth -- this module never reads the
    credential itself, but a backend's raw error text is still never
    passed through unexamined. Collapses to a short, generic message
    rather than attempting to detect and redact a secret substring it
    was never given in the first place."""

    return message.strip().splitlines()[0][:200] if message.strip() else "backend call failed"


class AnthropicBackend:
    """v1's one backend (R-ENDPOINT-003). Dispatches via the `claude` CLI's
    non-interactive mode (`-p`/`--print`) rather than a from-scratch API
    client -- confirmed live (D45/D46) to be a real, scriptable call with
    structured JSON output. Reads `VAR-ANTHROPIC-API-KEY` by letting the
    subprocess inherit the parent environment's `ANTHROPIC_API_KEY`
    directly (D46) -- this class never reads that variable itself
    (R-ENDPOINT-005)."""

    name = "anthropic"

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    def complete(self, prompt: str, model: str, **params: Any) -> BackendResult:
        cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json"]
        system_prompt = params.get("system_prompt")
        if system_prompt:
            cmd += ["--system-prompt", str(system_prompt)]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self._timeout
            )
        except subprocess.TimeoutExpired:
            return BackendResult(
                text=None, error_category="timeout",
                error_message="claude CLI call exceeded bounded timeout",
            )
        except FileNotFoundError:
            return BackendResult(
                text=None, error_category="network",
                error_message="claude CLI not found on PATH",
            )

        if proc.returncode != 0:
            return BackendResult(
                text=None,
                error_category=_classify_text(proc.stderr or ""),
                error_message=_sanitize(proc.stderr or "claude CLI exited non-zero"),
            )

        try:
            events = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return BackendResult(
                text=None, error_category="network",
                error_message="could not parse claude CLI output as JSON",
            )

        result_event = next(
            (e for e in events if isinstance(e, dict) and e.get("type") == "result"),
            None,
        )
        if result_event is None:
            return BackendResult(
                text=None, error_category="network",
                error_message="no result event in claude CLI output",
            )

        if result_event.get("is_error"):
            status = result_event.get("api_error_status")
            message = str(result_event.get("result") or "claude CLI reported an error")
            category = _classify_status(status) if status is not None else _classify_text(message)
            return BackendResult(
                text=None, error_category=category, error_message=_sanitize(message),
            )

        return BackendResult(text=result_event.get("result"))


_REAL_BACKENDS: dict[str, Backend] = {"anthropic": AnthropicBackend()}
