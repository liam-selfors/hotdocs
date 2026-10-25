# AC-UI-001

Covers: R-UI-001
Kind: generated-test

```gherkin
Given a built page and a .hotdocs/tracking/ directory with one real
  TrackingRecord file, opened in an actual browser environment
When the page loads
Then DuckDB-WASM's core read_json (no extension loaded) successfully
  queries the record directly, with no server request made
```
