# AC-GRAPH-005

Covers: R-GRAPH-005
Kind: compiled

```gherkin
Given one declared var with no component referencing it via uses_var
When build_corpus_graph runs
Then aggregates.orphan_var_rate reflects that one orphan
```
