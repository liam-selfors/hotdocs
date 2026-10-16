# AC-MERGE-005

Covers: R-MERGE-005
Kind: compiled

```gherkin
Given a mock generator/verifier-orchestrator pair where the first sample
  fails and the second passes, with k=3
When run_merge is called
Then generator is called exactly twice, and the recorded sample_index is
  the second attempt's
```
