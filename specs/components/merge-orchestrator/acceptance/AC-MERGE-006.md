# AC-MERGE-006

Covers: R-MERGE-006
Kind: compiled

```gherkin
Given a mock verifier-orchestrator that always returns fail, with k=2
When run_merge is called
Then generator is called exactly twice and the component's merge is blocked
```
