# AC-TRACK-010

Covers: R-TRACK-010
Kind: generated-test

```gherkin
Given every component in scope is a provenance-checker hit with a
  passing verification_report, and every intersecting capability's
  run_capability_gates call reports a passing CapabilityProvenanceCheckResult
When check_readiness is called
Then ready is true and not_ready_reasons is empty

Given every component passes but one intersecting capability's
  run_capability_gates call reports a failure
When check_readiness is called
Then ready is false and not_ready_reasons names that capability,
  despite every component passing

Given an intersecting capability that is a provenance miss and model
  is None
When check_readiness is called
Then it reports a usage error for that capability rather than skipping
  it or running run_capability_gates without a model
```
