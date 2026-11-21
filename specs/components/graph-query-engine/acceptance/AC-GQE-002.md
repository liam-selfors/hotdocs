# AC-GQE-002

Covers: R-GQE-002
Kind: generated-test

```gherkin
Given the fixture corpus of specs/architecture/graph-query-engine-fixture.md
  written under a temporary repo_root
When load_views runs and edges is queried
Then the row count per edge_type is depends_on 1, realizes 2, uses_var
  1, depends_on_guarantees 1, covers 3, supersedes 1 and builds_on 1
```
