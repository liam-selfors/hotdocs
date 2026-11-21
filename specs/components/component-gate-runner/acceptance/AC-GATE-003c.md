# AC-GATE-003c

Covers: R-GATE-003
Kind: generated-test

```gherkin
Given a provenance miss and a faked run_attempts returning passed false,
  stop_reason "not_retried", one attempt with outcome
  "generation_failed", a generation result with empty files and
  model_call_error {"category": "timeout", "message": "t"}, and no
  verification report
When run_component_gates is called
Then blocked is true with block_reason "model_call_error",
  model_call_error is that error, and verification is null
```
