# AC-GATE-003a

Covers: R-GATE-003
Kind: generated-test

```gherkin
Given a provenance miss, a faked generator returning one file, and a
  faked verify returning overall "pass"
When run_component_gates is called
Then generator was called exactly once, blocked is false, block_reason
  and model_call_error are null, and verification.overall is "pass"
```
