# AC-GRAPH-002

Covers: R-GRAPH-002
Kind: generated-test

```gherkin
Given comp-a with depends_on [comp-b], realizes [P-ONE] and uses_var
  [VAR-ONE], comp-b with none, capability P-ONE and var VAR-ONE
When build_corpus_graph runs
Then edges is exactly [{"from": "comp-a", "to": "P-ONE", "kind":
  "realizes"}, {"from": "comp-a", "to": "VAR-ONE", "kind": "uses_var"},
  {"from": "comp-a", "to": "comp-b", "kind": "depends_on"}], sorted by
  from, to, kind
```
