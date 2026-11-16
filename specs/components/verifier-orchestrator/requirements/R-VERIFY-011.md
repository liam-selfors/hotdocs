# R-VERIFY-011

**R-VERIFY-011** — The `VerificationReport` MUST include a
  `requirement_results` field: one `pass`/`fail` entry per `R-id` the
  component declares, computed by projecting each criterion's own
  `result` onto the `R-id`(s) it `Covers:` — the traceability edges
  `R-LINT-008`/`009` enforce and `corpus-graph-builder` materializes,
  reused rather than recomputed. A requirement is `pass` only if
  **every** criterion covering it is `pass`; **any** covering criterion
  that is `fail` or `skipped` makes it `fail`, since "not fully
  demonstrated" and "demonstrated wrong" both mean unverified.

  `requirement_results` MUST contain **only** `R-id` keys and
  `pass`/`fail` values — never a criterion's Gherkin text, `rationale`,
  expected/actual values, or anything else that could let a consumer
  reconstruct what a specific test checked. That keeps
  `spec-bundle-assembler`'s R-ASSEMBLE-001 exclusion of `acceptance/`
  from being undone through this field, whoever reads it.
