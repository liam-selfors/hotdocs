# AC-CORPUS-004

Covers: R-CORPUS-001
Kind: generated-test

```gherkin
Given a corpus whose requirements/R-FOO-001.md has no frontmatter and
  whose component.md has one, under a repo_root with no gen/ directory
When load_corpus(repo_root) runs
Then the requirement's Doc has has_frontmatter False, frontmatter {}
  and body equal to the file's whole text; the component.md Doc has
  has_frontmatter True; and corpus.graph answers
  "SELECT count(*) FROM nodes", graph-query-engine having been loaded
  from the tool root
```
