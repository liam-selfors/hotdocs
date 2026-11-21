# Capability Scenario Verifier — Non-Functional Constraints

- **Determinism of dispatch, not of everything dispatched to.** This
  component's own capability-intersection lookup and aggregation MUST be
  deterministic given the same blast radius and corpus state; an injected
  `llm-judge` or `test_author` callable's output is not covered.
- **`kind:` is read-only input, never written.** Same invariant
  `verifier-orchestrator` honors: a capability scenario's declared `kind`
  is fixed at spec-authoring time and never reinterpreted here.
- **Never conflated with a single component's own verification result.**
  `CapabilityScenarioReport` is a distinct namespace (`P-id`-keyed) from
  any component's `VerificationReport`.
- **Never a pass without a run.** A `compiled` or `generated-test`
  scenario passes only when its test actually ran and exited `0`
  (`R-SCENARIO-005`); producing a test, or compiling one, is not a pass.
- **A failure is recorded, never hidden.** A failing capability is
  written to its record and returned like a passing one, and a recorded
  failure is a hit until the code it was computed against changes.
- **Fail closed on the key.** Any doubt about a record — absent,
  unreadable, from another `gate_version`, or hashed over different
  content — is a miss, never a hit.
