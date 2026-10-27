# AC-UI-004

Covers: R-UI-004
Kind: generated-test

```gherkin
Given the rendered page's source
When inspected for its data sources
Then it reads corpus-graph.json (topology) and provenance-tracker's
  VerifyReport/AttemptRecord data (status) — and nothing under specs/,
  gen/, or verification/ directly — and writes to none of them
```
