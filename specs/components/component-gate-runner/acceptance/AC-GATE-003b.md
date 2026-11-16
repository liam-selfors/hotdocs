# AC-GATE-003b

Covers: R-GATE-003
Kind: generated-test

```gherkin
Given a provenance miss and a faked run_attempts returning passed false
  after three attempts, the last with outcome "verification_failed"
When run_component_gates is called without retry_feedback
Then run_attempts was called exactly once, with retry_feedback None and
  max_attempts 3, and blocked is true with block_reason
  "verification_failed"
```
