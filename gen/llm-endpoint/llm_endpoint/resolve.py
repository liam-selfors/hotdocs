"""
Backend resolution (R-ENDPOINT-002).

A model identifier is resolved to its backend by naming pattern --
`claude-*` resolves to the Anthropic backend (v1's one implemented
backend, R-ENDPOINT-003). This is a deterministic function of the
identifier alone (see constraints.md); it never touches the network and
never falls back silently to whichever backend happens to be configured.

A caller never names or configures a backend itself, only a model -- an
identifier that resolves to nothing implemented fails immediately with
`UnknownModelBackendError`, a caller/configuration mistake caught before
any network call is attempted, deliberately never conflated with the
`model_call_error` vocabulary (R-ENDPOINT-004), which only covers a
dispatch that was actually attempted.
"""

from .backends.anthropic import AnthropicBackend


class UnknownModelBackendError(ValueError):
    """
    Raised when a model identifier does not resolve to any backend this
    component implements. A usage/configuration error, not a
    `model_call_error` -- no dispatch was attempted.
    """


_ANTHROPIC_BACKEND = AnthropicBackend()


def resolve_backend(model):
    """
    Resolve `model` to a backend callable, or raise
    `UnknownModelBackendError`. v1 implements exactly one backend
    (Anthropic, R-ENDPOINT-003); a future backend is addable here as a
    new branch of this same resolve/dispatch split, never a redesign of
    `complete()`'s contract.
    """
    if isinstance(model, str) and model.startswith("claude-"):
        return _ANTHROPIC_BACKEND

    raise UnknownModelBackendError(
        f"Model identifier {model!r} does not resolve to any backend "
        "implemented by llm-endpoint."
    )