# AC-TRACK-010

Covers: R-TRACK-010
Kind: generated-test

Every scenario that exercises `run_capability_gates` fakes
`check_capability_provenance` to return `hit` false for that
capability; a hit short-circuits before `run_capability_gates` is
ever called (`R-TRACK-010`). A faked provenance-checker provides
current_sealed_key (returning None), current_provenance_key,
check_provenance, and check_sealed_provenance.

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

Given every component passes and an intersecting capability P-FOO is a
  provenance miss, with model None
When check_readiness is called
Then it does not raise, ready is false, not_ready_reasons holds exactly
  "P-FOO: needs a fresh run; pass --model", every component appears in
  the report, and run_capability_gates was never called
```
