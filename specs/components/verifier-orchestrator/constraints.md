---
id: comp-verifier-orchestrator-constraints
title: Verifier Orchestrator — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# Verifier Orchestrator — Non-Functional Constraints

- **Determinism of orchestration, not of everything it orchestrates.** This
  component's own dispatch/aggregation logic MUST be deterministic
  (R-VERIFY-008); an injected `llm-judge` callable's actual judgments are
  explicitly not covered by that guarantee.
- **No bypassing `skipped`.** A `skipped` `llm-judge` result MUST never be
  silently converted to `pass` to make an overall verdict look cleaner —
  the distinction (R-VERIFY-005) is load-bearing for the multi-model
  coverage metric (`notes/metrics.md`) and must survive every aggregation
  step.
- **Performance.** `compiled` and `generated-test` checks, together, SHOULD
  complete in a time proportional to the component's own size caps (D2) —
  not independently bounded here, since it inherits whatever cost the
  underlying test execution has; no new budget is being set.
