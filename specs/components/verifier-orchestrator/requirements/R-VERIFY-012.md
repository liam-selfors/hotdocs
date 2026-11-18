# R-VERIFY-012

**R-VERIFY-012** — A `compiled` or `generated-test` criterion whose
  `result` is `fail` MUST carry `failure_detail`:
  `{message, expected, actual}`. `message` is a short description of
  what failed (an assertion summary, a traceback's final line).
  `expected`/`actual` carry the compared values of a direct equality or
  containment check, always for a `compiled` criterion, each as its
  original Python type, recovered with `ast.literal_eval`, never the
  string pytest renders (`D85`). For a `generated-test` assertion this
  component cannot interpret they MAY be `null`; `message` is still
  required. A `pass` or `skipped` criterion has no `failure_detail`,
  and it never reaches `requirement_results` or `retry_feedback`
  (`R-GEN-012`).
