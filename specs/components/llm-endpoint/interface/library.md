# Library

```
complete(prompt: str, model: str, **params) -> ModelResponse
```

Not a pure function — the one thing every call to this component does is
reach a network. `**params` passes through to whichever backend `model`
resolves to (e.g. `max_tokens`, `temperature`) — this component does not
interpret them, only forwards them; a backend rejecting an unsupported
param is that backend's own concern, surfaced as `model_call_error`
(`R-ENDPOINT-004`), not validated here.
