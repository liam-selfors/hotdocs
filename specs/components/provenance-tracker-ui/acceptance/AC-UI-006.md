# AC-UI-006

Covers: R-UI-006
Kind: generated-test

```gherkin
Given the built page exists at the configured --out directory and a
  request is made to the serve command's local server for a path other
  than the built page, corpus-graph.json, or a file under
  .hotdocs/attempts/
When the server handles that request
Then it returns 404 — confirming the server returns only the literal
  contents of those known static sources and computes no response of
  its own
```
