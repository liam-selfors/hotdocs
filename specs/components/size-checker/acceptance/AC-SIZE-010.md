# AC-SIZE-010

Covers: R-SIZE-001
Kind: generated-test

```gherkin
Given AC-SIZE-009's component comp-p, and beside it a directory
  specs/components/ghost/ holding only requirements/R-GHOST-001.md,
  exactly "# R-GHOST-001", "", "**R-GHOST-001** — x."
When check(repo_root) runs
Then it returns without raising, its findings are exactly those it
  returns with specs/components/ghost/ removed, and no finding's message
  or file names ghost
```
