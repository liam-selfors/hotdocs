# AC-MERGE-020

Covers: R-MERGE-005
Kind: compiled

```gherkin
Given a mock generator that returns model_call_error on the first call
  and succeeds (with a candidate verifier-orchestrator then passes) on
  the second, with k=2
When run_merge is called
Then generator is called exactly twice, the second call's retry_feedback
  argument is absent (not derived from a VerificationReport that never
  existed), and the component's merge succeeds using the second sample
```
