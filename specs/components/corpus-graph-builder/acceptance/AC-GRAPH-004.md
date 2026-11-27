# AC-GRAPH-004

Covers: R-GRAPH-004
Kind: generated-test

```gherkin
Given capabilities P-ONE, P-TWO and P-THREE, comp-a with
  realizes [P-ONE], comp-b with no relations, comp-c
  with depends_on [comp-b], and comp-d with no relations
When build_corpus_graph runs
Then aggregates.orphan_capability_rate is 2/3 and
  aggregates.orphan_component_rate is 0.5 (comp-c and comp-d are
  orphaned; comp-a realizes and comp-b is depended on)

Given a corpus with one component and no capabilities
When build_corpus_graph runs
Then orphan_capability_rate is 0.0
```
