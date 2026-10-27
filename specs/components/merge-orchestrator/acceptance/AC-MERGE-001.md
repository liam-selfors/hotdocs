# AC-MERGE-001

Covers: R-MERGE-001
Kind: generated-test

```gherkin
Given a corpus with a hard-fail spec-linter finding
When run_merge is called
Then the merge is blocked before impact-analyzer or any other component is
  invoked
```
