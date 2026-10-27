# AC-DOCS-002

Covers: R-DOCS-002
Kind: generated-test

```gherkin
Given a component node carrying a full detail payload (spec content,
  R-ids, criteria, provenance, size status, sealed status, owners)
When render_docs_site runs
Then that component's detail view includes every one of those fields
```
