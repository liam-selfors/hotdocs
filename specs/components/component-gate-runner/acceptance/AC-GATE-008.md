# AC-GATE-008

Covers: R-GATE-008
Kind: generated-test

```gherkin
Given a non-sealed, cache-miss component whose generator/verifier-orchestrator
  calls have concluded
When run_component_gates is called
Then merge-tracker's write_attempt_record is called exactly once with
  the full GenerationResult and, if reached, the full
  VerificationReport, and a failure in that call does not change this
  component's own result
```
