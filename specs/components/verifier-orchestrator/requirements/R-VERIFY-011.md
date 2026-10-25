# R-VERIFY-011

**R-VERIFY-011** — The `VerificationReport` MUST include a
  `requirement_results` field: one `pass`/`fail` entry per `R-id` the
  component declares, computed by projecting each criterion's own `result`
  (per `criteria`) onto the `R-id`(s) it `Covers:` — the same traceability
  edges `R-LINT-008`/`009` already enforce and `corpus-graph-builder`
  already materializes, reused here rather than independently recomputed.
  A requirement is `pass` only if **every** criterion covering it is
  `pass`; **any** covering criterion that is `fail` or `skipped` makes that
  requirement `fail` — "not fully demonstrated" is treated the same as
  "demonstrated to be wrong" for this purpose, since both mean the
  requirement isn't verified yet.

  `requirement_results` MUST contain **only** `R-id` keys and `pass`/`fail`
  values — never a criterion's Gherkin text, its `rationale` (for
  `llm-judge` criteria), its expected/actual values, or any other content
  that could let a consumer reconstruct what a specific test checked.

  This boundary predates, and outlives, `D31`'s retirement of automatic
  retry — it was never only about feeding that loop. `requirement_results`
  is a standalone requirement-level summary, useful to a human or review
  packet on its own, and — since `D33` restored `retry_feedback` as a
  developer-supplied input (via `R-TRACK-008`) rather than an automatic
  one — also what a developer now reads to decide what to supply.
  Keeping it content-free regardless of who reads it protects
  `spec-bundle-assembler`'s R-ASSEMBLE-001 exclusion of `acceptance/`
  against ever being reconstituted through this field by any consumer.
