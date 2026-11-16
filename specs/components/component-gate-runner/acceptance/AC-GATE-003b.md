# AC-GATE-003b

Covers: R-GATE-003
Kind: generated-test

```gherkin
Given a provenance miss, a faked generator returning one file, and a
  faked verify returning overall "fail" with requirement_results
  {"R-FOO-001": "pass", "R-FOO-002": "fail"}
When run_component_gates is called without retry_feedback
Then generator was called exactly once, with retry_feedback None, and
  blocked is true with block_reason "verification_failed"
```
