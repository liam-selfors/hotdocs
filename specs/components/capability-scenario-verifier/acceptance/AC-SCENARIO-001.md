# AC-SCENARIO-001

Covers: R-SCENARIO-001
Kind: compiled

```gherkin
Given a blast radius of two components, both already regenerated and
  passed their own per-component verification, and one product capability
  whose realizes-set includes both, with exactly one capability scenario
When run_capability_scenarios is called with that blast radius
Then that capability's scenario is run against the real assembled gen/
  output, dispatched via criterion-compiler/test_author/judge exactly as
  verifier-orchestrator's own criteria are, and the result is keyed by
  that capability's P-id, distinct from either component's own
  verification result
```
