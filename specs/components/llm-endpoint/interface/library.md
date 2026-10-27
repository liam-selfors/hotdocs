# Library

```
complete(prompt: str, model: str, *, backend=None, **params) -> ModelResponse
```

Not a pure function — the one thing every call to this component does is
reach a network. `**params` passes through to whichever backend `model`
resolves to (e.g. `max_tokens`, `temperature`) — this component does not
interpret them, only forwards them; a backend rejecting an unsupported
param is that backend's own concern, surfaced as `model_call_error`
(`R-ENDPOINT-004`), not validated here.

`backend` (added `D33`, the same injectable-callable pattern `spec-linter`'s
`judge` parameter and `verifier-orchestrator`'s `judge`/`test_author`
parameters already establish) — omitted (the default), `complete()`
resolves a real backend internally per `R-ENDPOINT-002`; a caller
supplying one bypasses resolution entirely, for exactly one reason:
`AC-ENDPOINT-002`/`003`/`006` require testing this component's own
dispatch/classification/logging logic against an injected mock backend,
never a real network call. Not documented in the original interface
spec — a real, pre-existing gap, fixed now rather than propagated
further, the same way `provenance-writer`'s `ProvenanceInputs` gap was.
