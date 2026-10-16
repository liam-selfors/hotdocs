# R-VERIFY-002

**R-VERIFY-002** — For every `generated-test`-kind criterion, this
  component MUST obtain the test code — from cache if already authored for
  this criterion's content, or by dispatching to an injectable
  `test_author` callable otherwise (R-VERIFY-009) — execute it against
  `gen/<component>/`, and record a pass/fail per criterion.
