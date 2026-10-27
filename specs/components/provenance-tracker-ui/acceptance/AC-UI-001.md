# AC-UI-001

Covers: R-UI-001
Kind: generated-test

```gherkin
Given a built page, a real corpus-graph.json, and a real
  .hotdocs/attempts/ directory, served by the local static-file server
  (R-UI-006) and opened in an actual browser environment
When the page loads
Then DuckDB-WASM's duckpgq-extended graph query successfully renders
  the corpus-graph.json topology, and read_json successfully queries
  the attempts data — the server only returned literal bytes for both,
  it computed no part of either query itself
```
