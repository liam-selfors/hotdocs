# R-VERIFY-010

**R-VERIFY-010** — Unlike a `skipped` `llm-judge` finding, a
  `generated-test` criterion with no cached test and no `test_author`
  configured MUST be recorded as `fail`, not `skipped`. `llm-judge` is
  for qualities no test could capture, so "not evaluated" is a
  legitimate, visible gap; a `generated-test` criterion exists because
  a real, mutation-tested check is possible, so an unauthored one is a
  verification gap the mutation-score gate (R-VERIFY-006) presumes
  absent.
