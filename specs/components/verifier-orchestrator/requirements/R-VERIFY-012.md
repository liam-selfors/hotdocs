# R-VERIFY-012

**R-VERIFY-012** — A `compiled` or `generated-test` criterion whose
  `result` is `fail` MUST carry `failure_detail`:
  `{message, expected, actual}`. `message` is a short description of
  what failed.
  `expected`/`actual` carry the compared values of a direct equality or
  containment check, always for a `compiled` criterion, each as its
  original Python type, recovered with `ast.literal_eval`, never the
  string pytest renders (`D85`); for a `generated-test` assertion this
  component cannot interpret they MAY be `null`. A `pass` or `skipped`
  criterion has no `failure_detail`.
