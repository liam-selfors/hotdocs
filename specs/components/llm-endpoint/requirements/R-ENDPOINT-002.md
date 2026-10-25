# R-ENDPOINT-002

**R-ENDPOINT-002** — MUST resolve a model identifier to its backend
  internally (e.g. by naming pattern — `claude-*` resolves to the
  Anthropic backend); a caller never names or configures a backend
  itself, only a model. An identifier that resolves to no implemented
  backend MUST fail immediately with a specific usage error — never a
  silent fallback to whichever backend happens to be configured, and
  never conflated with `model_call_error` (`R-ENDPOINT-004`): this is a
  caller/configuration mistake, caught before any network call is
  attempted, not a transient failure of one that was.
