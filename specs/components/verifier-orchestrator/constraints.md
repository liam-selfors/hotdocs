# Verifier Orchestrator — Non-Functional Constraints

- **Determinism of orchestration, not of what it orchestrates.** This
  component's own dispatch and aggregation MUST be deterministic
  (R-VERIFY-008); an injected `llm-judge` or `test_author` callable's
  output is not covered.
- **`kind:` is read-only input.** Neither this component nor
  `test_author` MAY alter a criterion's declared `kind`.
- **No bypassing `skipped` or the `generated-test`/`llm-judge` `fail`
  asymmetry.** A `skipped` `llm-judge` result MUST never become `pass`,
  and an unauthored `generated-test` result MUST never become `skipped`
  (R-VERIFY-005/010).
