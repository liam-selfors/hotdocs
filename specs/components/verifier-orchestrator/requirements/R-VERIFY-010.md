# R-VERIFY-010

**R-VERIFY-010** — Unlike a `skipped` `llm-judge` finding, a
  `generated-test` criterion with no cached test and no `test_author`
  configured MUST be recorded as `fail`, not `skipped`. The two `kind`s
  differ in exactly this way: `llm-judge` is for qualities no test could
  capture even in principle, so "not evaluated" is a legitimate, visible
  gap. A `generated-test` criterion exists specifically
  *because* a real, mutation-tested check is possible for it — an
  unauthored one isn't a degraded-but-acceptable state, it's a verification
  gap the mutation-score gate (R-VERIFY-006) already presumes doesn't
  exist.
