# Capability Scenario Verifier — Non-Functional Constraints

- **Determinism of dispatch, not of everything dispatched to.** This
  component's own capability-intersection lookup and aggregation MUST be
  deterministic given the same blast radius and corpus state; an injected
  `llm-judge` or `test_author` callable's output is not covered.
- **`kind:` is read-only input, never written**: a capability
  scenario's declared `kind` is never reinterpreted here.
