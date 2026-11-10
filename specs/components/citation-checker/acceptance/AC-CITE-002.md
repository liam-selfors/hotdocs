# AC-CITE-002

Covers: R-CITE-002
Kind: generated-test

```gherkin
Given a live requirement citing a real file's "Query surface" section,
  and another citing the same file's "Nonexistent Heading" section
When check(repo_root) runs
Then only the second citation gets a R-CITE-002 finding
```
