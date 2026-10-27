# R-VERIFY-012

**R-VERIFY-012** — A `compiled` or `generated-test` criterion whose
  `result` is `fail` MUST additionally carry a `failure_detail` field:
  `{message, expected, actual}`. `message` is a short, human-readable
  description of what failed (an assertion summary, a traceback's final
  line). `expected`/`actual` carry the compared values whenever the
  underlying check is a direct equality/containment match — always
  populated for a `compiled` criterion, since the step-phrase grammar's
  own assertion templates (`specs/architecture/step-phrase-grammar.md`)
  already name what was compared. **Each value MUST be its original
  Python type** (`D85`) — an int, float, bool, or `None` compared
  value MUST NOT be left as the raw string pytest's own failure text
  renders it as; a parser that can locate the compared values at all
  MUST also recover their real type (e.g. via `ast.literal_eval` on the
  located substring), since `5 == 5` and `"5" == "5"` are a materially
  different fact for a human comparing this field against the
  generated code. `expected`/`actual` MAY be `null` for
  a `generated-test` criterion whose test code made an assertion this
  component cannot structurally interpret, in which case `message`
  alone is still required. A `pass` or `skipped` criterion's
  `failure_detail` MUST be absent — this field answers "what exactly
  failed," not "why it passed."

  This mirrors `llm-judge`'s `rationale` field (`SPEC_GUIDELINES.md` §5)
  one `kind` family over: every `kind` that can fail now carries its own
  structured account of why, not just the judgment-based one.

  `failure_detail` MUST NOT reach `requirement_results` — R-VERIFY-011's
  existing content boundary already excludes expected/actual values from
  that field, and this requirement does not reopen it. `failure_detail`
  is exposed on `criteria[]` for provenance/review-packet/human
  consumption only; it MUST NOT reach `retry_feedback`'s `R-id`-only
  channel (`R-GEN-012`).
