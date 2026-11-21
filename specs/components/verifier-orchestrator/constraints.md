# Verifier Orchestrator — Non-Functional Constraints

- **Determinism of orchestration, not of what it orchestrates.** This
  component's own dispatch and aggregation MUST be deterministic
  (R-VERIFY-008); an injected `llm-judge` or `test_author` callable's
  output is not covered.
- **`kind:` is read-only input.** Neither this component nor
  `test_author` MAY alter a criterion's declared `kind`.
