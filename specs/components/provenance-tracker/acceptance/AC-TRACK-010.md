# AC-TRACK-010

Covers: R-TRACK-010
Kind: generated-test

```gherkin
Given every component in scope's run_component_gates call reports a
  passing ComponentPipelineResult, and every intersecting capability's
  run_capability_gates call reports a passing CapabilityProvenanceCheckResult
When check_readiness is called
Then ready is true and not_ready_reasons is empty

Given every component passes but one intersecting capability's
  run_capability_gates call reports a failure
When check_readiness is called
Then ready is false and not_ready_reasons names that capability,
  despite every component passing
```
