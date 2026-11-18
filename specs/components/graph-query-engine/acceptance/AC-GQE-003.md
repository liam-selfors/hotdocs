# AC-GQE-003

Covers: R-GQE-003
Kind: generated-test

```gherkin
Given the fixture corpus of specs/architecture/graph-query-engine-fixture.md
  written under a temporary repo_root
When load_views runs and component_docs is queried
Then it has 2 rows, and comp-foo's row has title "Foo", depends_on
  ["comp-bar"] and a body containing "one two three"
```
