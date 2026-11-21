# AC-DOCS-004

Covers: R-DOCS-004
Kind: generated-test

```gherkin
Given only corpus-graph.json as input, with no other files available
When render_docs_site runs
Then it completes successfully, reading no file except its own asset
  static/app.js
```
