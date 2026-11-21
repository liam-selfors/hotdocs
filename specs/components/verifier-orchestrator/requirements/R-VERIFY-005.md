# R-VERIFY-005

**R-VERIFY-005** — The overall verdict MUST be `fail` if any `compiled` or
  `generated-test` criterion fails, the interface drift check fails, or
  an evaluated `llm-judge` criterion fails. A `skipped` `llm-judge`
  criterion alone MUST NOT cause `fail`: it was not evaluated.
