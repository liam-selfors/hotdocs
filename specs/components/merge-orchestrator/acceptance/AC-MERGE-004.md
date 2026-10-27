# AC-MERGE-004

Covers: R-MERGE-004
Kind: generated-test

```gherkin
Given a cache miss for an impacted component with one generated-test-kind
  criterion lacking a cached test
When run_merge is called
Then verifier-orchestrator is invoked with a real test_author callable
  backed by test-author, not a mock or an omitted parameter
```
