# AC-GRAPH-011

Covers: R-GRAPH-003
Kind: generated-test

```gherkin
Given comp-a whose component.md has the frontmatter owners: [team-x]
  and whose directory also holds requirements/R-A-001.md and
  interface/library.md
When build_corpus_graph runs
Then comp-a's node has owners ["team-x"], and documents whose keys are
  exactly "component.md", "interface/library.md" and
  "requirements/R-A-001.md", each mapped to that file's whole text
```
