# AC-GRAPH-009

Covers: R-GRAPH-009
Kind: generated-test

```gherkin
Given comp-foo has a provenance manifest at
  verification/comp-foo/.provenance.json with license_scan.flagged: true,
  and no other change to comp-foo's spec bundle
When corpus-graph-builder runs
Then comp-foo's node in verification/corpus-graph.json carries that flag
  — read via the component_provenance view directly over the manifest
  already written by provenance-writer, with no separate call into
  license-scanner's own output
```
