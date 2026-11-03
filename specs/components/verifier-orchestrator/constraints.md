# Verifier Orchestrator — Non-Functional Constraints

- **Determinism of orchestration, not of what it orchestrates.** This
  component's own dispatch and aggregation MUST be deterministic
  (R-VERIFY-008); an injected `llm-judge` or `test_author` callable's
  output is not covered.
- **`kind:` is read-only input.** This component and `test_author` MUST
  NOT alter or reinterpret a criterion's declared `kind`; it is fixed at
  spec-authoring time and lint-checked.
- **No bypassing `skipped` or the `generated-test`/`llm-judge` `fail`
  asymmetry.** A `skipped` `llm-judge` result MUST never become `pass`,
  and an unauthored `generated-test` result MUST never become `skipped`
  (R-VERIFY-005/010); the distinction is load-bearing for the
  multi-model coverage metric (`notes/metrics.md`).
- **Performance.** Checks SHOULD take time proportional to the
  component's own size caps (`D17`); no new budget is set.
