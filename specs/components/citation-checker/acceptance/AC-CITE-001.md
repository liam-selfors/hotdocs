# AC-CITE-001

Covers: R-CITE-001
Kind: generated-test

```gherkin
Given a live component.md citing a decision number with no
  corresponding specs/decisions/ file, and a second citing D7, one of
  D1-D14, never formalized as files
When check(repo_root) runs
Then only the first citation gets a R-CITE-001 finding
```
