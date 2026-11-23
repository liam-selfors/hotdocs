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

Given every component passes but intersecting capability P-FOO's
  run_capability_gates call returns hit false and the report
  {"P-FOO": {"overall": "fail", "scenarios": [
  {"id": "CS-FOO-001", "kind": "compiled", "result": "pass"},
  {"id": "CS-FOO-002", "kind": "llm-judge", "result": "fail"},
  {"id": "CS-FOO-003", "kind": "llm-judge", "result": "skipped"},
  {"id": "CS-FOO-004", "kind": "generated-test", "result": "fail"}]}}
When check_readiness is called
Then ready is false and not_ready_reasons is exactly the one entry
  "P-FOO: capability scenarios failed: CS-FOO-002, CS-FOO-004"

Given the same, but the report is {"P-FOO": {"overall": "fail", "scenarios": []}}
When check_readiness is called
Then ready is false and not_ready_reasons is exactly the one entry
  "P-FOO: has no capability scenarios; add a CS- scenario to its file under specs/product/"

Given every component passes and check_capability_provenance returns
  hit true with that same empty-scenarios report for P-FOO
When check_readiness is called
Then not_ready_reasons is that same one entry and run_capability_gates
  was never called

Given every component passes and an intersecting capability P-FOO is a
  provenance miss, with model None
When check_readiness is called
Then it does not raise, ready is false, not_ready_reasons holds exactly
  "P-FOO: needs a fresh run; pass --model", every component appears in
  the report, and run_capability_gates was never called
```
