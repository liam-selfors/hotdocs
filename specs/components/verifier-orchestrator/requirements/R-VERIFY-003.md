# R-VERIFY-003

**R-VERIFY-003** — For every `llm-judge`-kind criterion, this component
  MUST invoke an injectable judge callable **exactly once** with the
  `CriterionBundle` `spec-bundle-assembler`'s
  `assemble_criterion(component_id, criterion_id, repo_root)` returns, and record its pass/fail and rationale, or
  `skipped` when no judge is configured (`D65`).
