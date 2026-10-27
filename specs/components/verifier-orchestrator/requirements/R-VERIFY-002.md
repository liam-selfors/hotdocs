# R-VERIFY-002

**R-VERIFY-002** — For every `generated-test`-kind criterion, this
  component MUST obtain the test code — from cache if already authored for
  this criterion's content, or by dispatching to an injectable
  `test_author` callable otherwise (R-VERIFY-009) — execute it against
  `gen/<component>/`, and record a pass/fail per criterion.

  "From cache" here means: this component itself MUST check, before
  ever calling `test_author`, whether the glossary's "Criterion test
  filename" (`D63`) already exists directly under
  `verification/<component>/generated-test/` for this criterion — never
  a separate, self-invented cache location or naming scheme (a content
  hash, a nested subdirectory) — and use it as-is if so. This is a
  file-presence check this component performs itself, distinct from
  (and prior to) whatever internal cache `test_author` may consult on
  its own side when it IS dispatched (`R-AUTHOR-004`/`005`).
