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
  that could let a consumer reconstruct what a specific test checked. This
  boundary exists specifically so `requirement_results` can safely feed
  `generator`'s retry mechanism (R-GEN-010) without reopening
  `spec-bundle-assembler`'s R-ASSEMBLE-001 exclusion of `acceptance/` from
  what a generation model ever sees — a requirement's own normative text is
  already in the model's bundle via `requirements/`; a bare pass/fail
  discloses nothing beyond "your attempt didn't satisfy text you already
  had," regardless of which `kind` of criterion covers it.
