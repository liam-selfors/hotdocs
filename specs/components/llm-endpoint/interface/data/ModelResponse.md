# `ModelResponse`

```json
{
  "text": "...",
  "model": "anthropic:claude-sonnet-5-5",
  "backend": "anthropic",
  "model_call_error": null
}
```

A failed call looks like:

```json
{
  "text": null,
  "model": "claude-sonnet-5",
  "backend": "anthropic",
  "model_call_error": { "category": "rate_limit", "message": "429 from backend" }
}
```

Exactly one of `text` or `model_call_error` is populated, never both and
never neither. `model_call_error.category` MUST be one of
`R-ENDPOINT-004`'s four values (`network`/`auth`/`rate_limit`/`timeout`),
never a bare boolean (`D20`). `message` is a short, backend-agnostic
description — never the raw vendor exception text or anything from
`R-ENDPOINT-005`'s credential boundary. `model` is the identifier exactly
as the caller passed it, prefix included (`R-ENDPOINT-002`). `backend` is
the provider name (`claude-cli`, `anthropic`, `openai`,
`openai-compatible`, `gemini`, `ollama`; a mock's own name when
injected), recorded on the output, never a caller input.
