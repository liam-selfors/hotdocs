# AC-GATE-008

Covers: R-GATE-008
Kind: generated-test

```gherkin
Given a non-sealed, cache-miss component whose generator/verifier-orchestrator
  calls have concluded
When run_component_gates is called
Then one AttemptRecord is written directly to
  .hotdocs/attempts/<component_id>/ with the full GenerationResult and,
  if reached, the full VerificationReport — no call is made into
  provenance-tracker's own code — and a failure writing that file does
  not change this component's own result
```
