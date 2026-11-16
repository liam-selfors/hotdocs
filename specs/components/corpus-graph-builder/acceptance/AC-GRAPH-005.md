# AC-GRAPH-005

Covers: R-GRAPH-005
Kind: generated-test

```gherkin
Given vars VAR-ONE and VAR-TWO and comp-a with uses_var [VAR-ONE]
When build_corpus_graph runs
Then aggregates.orphan_var_rate is 0.5

Given a corpus with no specs/vars/ directory
When build_corpus_graph runs
Then orphan_var_rate is 0.0
```
