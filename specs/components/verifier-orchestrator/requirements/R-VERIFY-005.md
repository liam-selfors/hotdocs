# R-VERIFY-005

**R-VERIFY-005** — The overall verdict MUST be `fail` if any `compiled` or
  `generated-test` criterion fails, or the interface drift check fails, or
  any `llm-judge` criterion is evaluated and fails. A `skipped` `llm-judge`
  finding MUST NOT by itself cause an overall `fail` — `skipped` means "not
  evaluated," not "violated," consistent with `spec-linter`'s existing
  severity semantics.
