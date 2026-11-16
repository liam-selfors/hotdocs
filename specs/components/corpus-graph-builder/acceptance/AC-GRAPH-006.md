# AC-GRAPH-006

Covers: R-GRAPH-006
Kind: generated-test

```gherkin
Given a corpus with comp-a and a snapshot of every file under repo_root
When build_corpus_graph runs
Then no file was added or changed

When write_corpus_graph(graph, repo_root) then runs
Then it returns repo_root / "verification" / "corpus-graph.json", and
  that is the only file added or changed
```
