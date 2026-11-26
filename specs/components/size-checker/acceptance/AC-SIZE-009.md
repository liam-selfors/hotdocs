# AC-SIZE-009

Covers: R-SIZE-004
Kind: generated-test

```gherkin
Given a component whose component.md is exactly "---", "id: comp-p",
  "title: P", "status: draft", "owners: [t]", "---", "", "# P", "",
  "## Purpose", "", a line of 90 words, then "", "## Scope", "", "x."
When check(repo_root) runs
Then it reports exactly one R-SIZE-004 finding, a warn with line 10
  whose message names 90
```
