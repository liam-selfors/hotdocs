# AC-GRAPH-010

Covers: R-GRAPH-010
Kind: generated-test

```gherkin
Given a repo_root holding comp-a and no gen/ directory, with every
  sys.path entry that names graph-query-engine removed and
  graph_query_engine popped from sys.modules for the test
When build_corpus_graph(repo_root) runs
Then it returns a graph whose nodes include comp-a
```
