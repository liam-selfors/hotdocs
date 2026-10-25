# AC-MERGE-006

Covers: R-MERGE-006
Kind: compiled

```gherkin
Given a mock verifier-orchestrator that always returns fail, with k=2
When run_merge is called
Then generator is called exactly twice and the component's merge is blocked

Given a mock generator that always returns model_call_error, with k=2
When run_merge is called
Then generator is called exactly twice (verifier-orchestrator is never
  invoked, since no candidate was ever produced) and the component's
  merge is blocked, with the block reason distinguishing "never produced
  a candidate" from "failed verification"
```
