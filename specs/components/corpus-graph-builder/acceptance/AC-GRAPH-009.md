# AC-GRAPH-009

Covers: R-GRAPH-009
Kind: generated-test

```gherkin
Given comp-a with verification/a/.provenance.json holding
  {"license_scan": {"blocked": true, "findings": ["GPL-3.0 in x.c"]},
  "verification_report": {"overall": "pass"}}, and no gen/license-scanner/
When build_corpus_graph runs
Then comp-a's provenance["license_scan"] is exactly {"blocked": true,
  "findings": ["GPL-3.0 in x.c"]}
```
