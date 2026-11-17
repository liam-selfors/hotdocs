# R-VERIFY-012

**R-VERIFY-012** — A `compiled` or `generated-test` criterion whose
  `result` is `fail` MUST additionally carry a `failure_detail` field:
  `{message, expected, actual}`. `message` is a short, human-readable
  description of what failed (an assertion summary, a traceback's final
  line). `expected`/`actual` carry the compared values whenever the
  underlying check is a direct equality/containment match — always
  populated for a `compiled` criterion, since the step-phrase grammar's
  assertion templates (`specs/architecture/step-phrase-grammar.md`) name
  what was compared. **Each value MUST be its original Python type**
  (`D85`): an int, float, bool, or `None` MUST NOT be left as the raw
  string pytest's failure text renders it as; a parser that can locate
  the compared values MUST recover their real type (e.g. via
  `ast.literal_eval`), since `5 == 5` and `"5" == "5"` differ.
  `expected`/`actual` MAY be `null` for a `generated-test` criterion
  whose assertion this component cannot structurally interpret, in which
  case `message` alone is still required. A `pass` or `skipped`
  criterion's `failure_detail` MUST be absent. It MUST NOT reach
  `requirement_results` or `retry_feedback` (`R-GEN-012`).
