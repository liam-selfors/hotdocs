# AC-MERGE-011

Covers: R-MERGE-011
Kind: compiled

```gherkin
Given one impacted component that exhausted retries and another that
  passed cleanly
When run_merge is called
Then the overall merge is blocked, with block_reasons naming the failed
  component
```
