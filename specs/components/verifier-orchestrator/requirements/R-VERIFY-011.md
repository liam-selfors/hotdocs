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

  This boundary predates, and outlives, `D31`'s retirement of
  `generator`'s retry mechanism — it was never only about feeding that
  loop. `requirement_results` is this component's own
  requirement-level summary of a verification run, useful on its own
  (a human or a review packet reading "which requirements failed," not
  just "which criteria") independent of whether anything downstream ever
  used it to drive a retry. Keeping it content-free the same way
  regardless protects `spec-bundle-assembler`'s R-ASSEMBLE-001 exclusion
  of `acceptance/` against ever being reconstituted through this field by
  *any* future consumer, not only the one that originally motivated the
  rule.
