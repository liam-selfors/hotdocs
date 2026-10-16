---
id: comp-verifier-orchestrator-constraints
title: Verifier Orchestrator — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# Verifier Orchestrator — Non-Functional Constraints

- **Determinism of orchestration, not of everything it orchestrates.** This
  component's own dispatch/aggregation logic MUST be deterministic
  (R-VERIFY-008); an injected `llm-judge` or `test_author` callable's
  actual output is explicitly not covered by that guarantee.
- **`kind:` is read-only input, never written.** This component (and
  `test_author`) MUST NOT alter, reinterpret, or override a criterion's
  declared `kind` at verification time — it is fixed at spec-authoring time
  in `acceptance.md` and lint-checked. A criterion's `kind` reaching this
  component is treated as ground truth, full stop.
- **No bypassing `skipped` or the `generated-test`/`llm-judge` `fail`
  asymmetry.** A `skipped` `llm-judge` result MUST never be silently
  converted to `pass`; an unauthored `generated-test` result MUST never be
  silently converted to `skipped` (R-VERIFY-010) — the distinction (R-VERIFY-
  005/010) is load-bearing for the multi-model coverage metric
  (`notes/metrics.md`) and must survive every aggregation step.
- **Performance.** `compiled` and `generated-test` checks, together, SHOULD
  complete in a time proportional to the component's own size caps (D2) —
  not independently bounded here, since it inherits whatever cost the
  underlying test execution has; no new budget is being set.
