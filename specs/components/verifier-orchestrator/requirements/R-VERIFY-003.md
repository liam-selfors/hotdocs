# R-VERIFY-003

**R-VERIFY-003** — For every `llm-judge`-kind criterion, this component
  MUST invoke an injectable judge callable **exactly once** with the
  same `CriterionBundle` `test_author` receives for that criterion
  (`R-VERIFY-009`), and record its pass/fail and rationale, or
  `skipped` when no judge is configured (`D65`).
