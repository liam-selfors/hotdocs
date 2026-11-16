# AC-GRAPH-004

Covers: R-GRAPH-004
Kind: generated-test

```gherkin
Given capabilities P-ONE and P-TWO, comp-a realizing P-ONE, comp-b with
  no relations, and comp-c with depends_on [comp-b]
When build_corpus_graph runs
Then aggregates.orphan_capability_rate is 0.5 and
  aggregates.orphan_component_rate is 1/3 (only comp-c is orphaned)

Given a corpus with one component and no capabilities
When build_corpus_graph runs
Then orphan_capability_rate is 0.0
```
