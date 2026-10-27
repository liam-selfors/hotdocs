# AC-MERGE-010

Covers: R-MERGE-010
Kind: generated-test

```gherkin
Given provenance-writer has completed for every impacted component
When run_merge is called
Then corpus-graph-builder and review-packet-builder are invoked exactly
  once each, not once per component
```
