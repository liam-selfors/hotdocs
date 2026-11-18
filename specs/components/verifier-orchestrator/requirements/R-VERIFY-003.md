# R-VERIFY-003

**R-VERIFY-003** — For every `llm-judge`-kind criterion, this component
  MUST invoke an injectable judge callable **exactly once**, passing
  exactly the same `CriterionBundle` `test_author` receives for that
  criterion (`R-VERIFY-009`) — never a separate, narrower payload — and
  record its pass/fail + rationale, or record `skipped` when no judge is
  configured (`D65`).
