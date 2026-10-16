# AC-GRAPH-007

Covers: R-GRAPH-007
Kind: compiled

```gherkin
Given a merge to main
When the pipeline runs
Then corpus-graph.json is rebuilt as part of that merge, not deferred to a
  later scheduled job
```
