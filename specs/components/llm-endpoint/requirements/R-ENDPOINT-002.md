# R-ENDPOINT-002

**R-ENDPOINT-002** — MUST resolve a model identifier to a provider
  internally. A caller names a model and nothing else, apart from the
  optional `hotdocs.toml` (`R-ENDPOINT-007`). An identifier is
  `<provider>:<model>` — the prefix counts only when it is one of
  `R-ENDPOINT-003`'s provider names, so `llama3.1:8b` is a bare name and
  `ollama:llama3.1:8b` is not — or a bare name. A bare name uses the
  provider `hotdocs.toml` configures; with no configuration, a bare name
  beginning `claude-` uses `claude-cli` and any other fails. A prefix
  naming a provider other than the configured one uses that provider's
  defaults.

  An identifier that resolves to no usable provider — an unconfigured
  non-`claude-` name, a prefix with no model after it, `openai-compatible`
  with no `base_url`, or an invalid configuration — MUST fail
  immediately with a specific usage error (`ModelResolutionError`):
  never a silent fallback to whichever provider happens to be
  configured, and never conflated with `model_call_error`
  (`R-ENDPOINT-004`), and raised before any call.

  The provider receives only the part after the prefix, but the
  returned `ModelResponse.model` MUST be the identifier exactly as the
  caller passed it, as callers record it in provenance.
