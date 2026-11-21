# R-VERIFY-002

**R-VERIFY-002** — For every `generated-test`-kind criterion, this
  component MUST obtain the test code, from cache or from `test_author`
  (R-VERIFY-009), execute it against `gen/<component>/`, and record a
  pass/fail per criterion.

  The cache is the glossary's "Criterion test filename" (`D63`) directly
  under `verification/<component>/generated-test/`, checked before
  calling `test_author` and used unless `R-VERIFY-019` finds it stale.
