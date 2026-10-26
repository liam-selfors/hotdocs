"""
The one entry point this entire component exposes (R-ENDPOINT-001).

`complete()` owns everything between a caller's request and a response
coming back: resolving `model` to a backend (R-ENDPOINT-002), dispatching
exactly once with no retry-with-backoff (R-ENDPOINT-004), and writing the
caller-agnostic call log (R-ENDPOINT-006) before returning. Prompt
construction and response parsing for any specific task stay with each
caller -- this component only knows "send this text to this model,
return what came back."
"""

from .call_log import write_call_record
from .model_response import ModelResponse
from .resolve import UnknownModelBackendError, resolve_backend

__all__ = ["complete", "UnknownModelBackendError"]


def complete(prompt, model, *, backend=None, **params):
    """
    complete(prompt, model, *, backend=None, **params) -> ModelResponse

    `model` is a required, vendor-agnostic string identifier -- never
    hardcoded to a canonical pin, never defaulted to a specific vendor.

    `backend`, omitted by default, resolves a real backend internally
    per R-ENDPOINT-002. A caller supplying one bypasses resolution
    entirely -- for injecting a mock backend in this component's own
    tests against its dispatch/classification/logging logic, never a
    real network call, and never a way for a generation/judge caller to
    pick its own vendor.

    `**params` passes through to whichever backend `model` resolves to
    untouched; this component does not interpret them.

    Raises `UnknownModelBackendError` immediately, before any network
    call and before any call-log write, if `model` resolves to no
    implemented backend -- a caller/configuration mistake, never
    conflated with a `model_call_error`.
    """
    dispatch = backend if backend is not None else resolve_backend(model)
    backend_name = getattr(dispatch, "name", None) or "injected"

    text, model_call_error = dispatch(prompt, model, **params)

    write_call_record(
        model=model,
        backend=backend_name,
        text_present=text is not None,
        model_call_error=model_call_error,
    )

    return ModelResponse(
        text=text,
        model=model,
        backend=backend_name,
        model_call_error=model_call_error,
    )