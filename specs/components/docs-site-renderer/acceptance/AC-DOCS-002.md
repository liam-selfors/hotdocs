# AC-DOCS-002

Covers: R-DOCS-002
Kind: generated-test

```gherkin
Given a component node whose documents, verification (with criteria
  and requirement_results), provenance, size_status, sealed,
  pinned_overrides and owners each hold a distinctive value
When render_docs_site runs
Then that component's detail view includes every one of those values
```
