# AC-GATE-003b

Covers: R-GATE-003
Kind: generated-test

```gherkin
Given a mock generator/verifier-orchestrator pair where the one call's
  candidate fails verification with requirement_results
  {"R-FOO-001": "pass", "R-FOO-002": "fail"}
When run_component_gates is called
Then generator is called exactly once for that component — never a
  second time with any form of feedback — and the result is blocked
  with a reason distinguishing "produced a candidate that failed
  verification" from a model_call_error
```
