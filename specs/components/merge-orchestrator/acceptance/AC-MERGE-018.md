# AC-MERGE-018

Covers: R-MERGE-017
Kind: compiled

```gherkin
Given three impacted components where the first fails verification
  (exhausts best_of_k) and the second and third would both pass
When run_merge is called
Then all three components are attempted to completion, and the
  MergeResult reports a result for every one of them, not just the first
  failure
```
