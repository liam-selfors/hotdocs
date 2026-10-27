# AC-GQE-007

Covers: R-GQE-007
Kind: generated-test

```gherkin
Given a DuckDB connection with load_views already called once
When load_views is called again on the same connection
Then it succeeds without error and every view still returns the same
  results as the first call
```
