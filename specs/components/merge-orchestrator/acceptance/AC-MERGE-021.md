# AC-MERGE-021

Covers: R-MERGE-019
Kind: generated-test

```gherkin
Given a merge attempt where one component is blocked
When run_merge completes
Then merge-tracker is called exactly once with overall "blocked" and a
  non-empty block_reasons, after review-packet-builder and regardless of
  the block decision — the call happens whether the merge passes or not
```
