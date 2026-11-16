# AC-GATE-003c

Covers: R-GATE-003
Kind: generated-test

```gherkin
Given a provenance miss and a faked generator returning empty files
  and model_call_error {"category": "timeout", "message": "t"}
When run_component_gates is called
Then generator was called exactly once, blocked is true with
  block_reason "model_call_error", model_call_error is that error, and
  verification is null
```
