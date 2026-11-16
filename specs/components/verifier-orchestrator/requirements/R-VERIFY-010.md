# R-VERIFY-010

**R-VERIFY-010** — Unlike a `skipped` `llm-judge` finding, a
  `generated-test` criterion with no cached test and no `test_author`
  configured MUST be recorded as `fail`, with `failure_origin` `"test"`,
  not `skipped`: a real, mutation-tested check was possible and is
  missing.
