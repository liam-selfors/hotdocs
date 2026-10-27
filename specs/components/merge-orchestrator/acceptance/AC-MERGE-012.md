# AC-MERGE-012

Covers: R-MERGE-012
Kind: generated-test

```gherkin
Given a merge that is not blocked
When run_merge completes
Then specs/, gen/, and verification/ are committed together in one
  squashed commit
```
