# AC-GATE-004

Covers: R-GATE-004
Kind: generated-test

```gherkin
Given a provenance miss and a faked generator returning a
  model_call_error
When run_component_gates is called
Then verify was never called and block_reason is "model_call_error"

Given a provenance miss, one generated file, and verify returning
  overall "fail"
When run_component_gates is called
Then block_reason is "verification_failed" and model_call_error is null
```
