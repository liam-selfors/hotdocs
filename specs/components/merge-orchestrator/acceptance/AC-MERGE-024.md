# AC-MERGE-024

Covers: R-MERGE-019
Kind: generated-test

```gherkin
Given a merge attempt where merge-tracker itself raises when called
When run_merge completes
Then MergeResult.tracking_write_error is populated, the merge's blocked
  value and block_reasons are unaffected by this failure, and the raised
  error is caught rather than propagating out of run_merge
```
