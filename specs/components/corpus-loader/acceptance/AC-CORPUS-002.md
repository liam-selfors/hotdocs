# AC-CORPUS-002

Covers: R-CORPUS-002
Kind: generated-test

```gherkin
Given the corpus of AC-CORPUS-001
When load_corpus(repo_root) runs
Then corpus.graph is a DuckDB connection, and
  "SELECT count(*) FROM nodes WHERE kind = 'component'" on it returns 1
```
