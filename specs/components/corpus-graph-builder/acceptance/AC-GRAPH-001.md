# AC-GRAPH-001

Covers: R-GRAPH-001
Kind: generated-test

```gherkin
Given a corpus, laid out as interface/library.md shows, with capabilities
  P-ONE and P-TWO, components comp-a, comp-b and comp-c (no relations),
  var VAR-ONE, a decision specs/decisions/D1.md, and a requirement file
  specs/components/a/requirements/R-A-001.md
When build_corpus_graph(repo_root) runs
Then nodes has exactly the keys P-ONE, P-TWO, comp-a, comp-b, comp-c and
  VAR-ONE, with type "capability" for the P- ids, "component" for the
  comp- ids and "var" for VAR-ONE
```
