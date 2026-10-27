# AC-MERGE-009

Covers: R-MERGE-009
Kind: generated-test

```gherkin
Given generation, verification, and both scans have completed for a
  component
When run_merge is called
Then provenance-writer is invoked for that component only after all of them
  have produced results
```
