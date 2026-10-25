# AC-UI-001

Covers: R-UI-001
Kind: generated-test

```gherkin
Given a built page and a .hotdocs/tracking/ directory with one real
  TrackingRecord file, served by the local static-file server (R-UI-006)
  and opened in an actual browser environment
When the page loads
Then DuckDB-WASM's core read_json (no extension loaded) successfully
  queries the record directly — the server only returned the record's
  literal bytes, it computed no part of the query itself
```
