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
never neither — mirroring `GenerationResult`'s existing
mutually-exclusive-fields convention rather than inventing a second one
for the same shape of outcome. `model_call_error.category` MUST be one
of `R-ENDPOINT-004`'s four values (`network`/`auth`/`rate_limit`/
`timeout`) — not a bare boolean, so `R-ENDPOINT-006`'s call log can
actually answer "how many failures this month were rate-limits vs. auth
errors," the question a flattened `true`/`false` could never answer
(`D20`). `message` is a short, backend-agnostic description — never the
raw vendor exception text or anything from `R-ENDPOINT-005`'s credential
boundary. `model` is the identifier exactly as the caller passed it, prefix
included (`R-ENDPOINT-002`). `backend` (added by `D20`) is the provider
name (`claude-cli`, `anthropic`, `openai`, `openai-compatible`,
`gemini`, `ollama`; a mock's own name when injected). It is never a
caller *input* — resolution stays internal to a `complete()` call — but
is recorded on the *output*, for the same observability
reason `model_call_error` needs real structure: "which backend is
flaky" is a question only answerable if the fact is captured somewhere.
