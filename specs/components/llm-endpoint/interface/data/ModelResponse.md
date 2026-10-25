# `ModelResponse`

```json
{
  "text": "...",
  "model": "claude-sonnet-5",
  "model_call_error": null
}
```

Exactly one of `text` or `model_call_error` is populated, never both and
never neither — mirroring `GenerationResult`'s existing
mutually-exclusive-fields convention rather than inventing a second one
for the same shape of outcome. `model` echoes back the identifier
actually dispatched to (never which backend it resolved to — that
resolution, per `R-ENDPOINT-002`, is this component's own internal
detail, invisible to callers and to anything recorded in provenance).
