# R-VERIFY-002

**R-VERIFY-002** — For every `generated-test`-kind criterion, this
  component MUST obtain the test code — from cache if already authored for
  this criterion's content, or by dispatching to an injectable
  `test_author` callable otherwise (R-VERIFY-009) — execute it against
  `gen/<component>/`, and record a pass/fail per criterion.

  "From cache" here means: before calling `test_author`, this component
  MUST itself check whether the glossary's "Criterion test filename"
  (`D63`) exists directly under `verification/<component>/generated-test/`
  — never a self-invented cache location or naming scheme — and use it
  unless `R-VERIFY-019` finds it stale.
