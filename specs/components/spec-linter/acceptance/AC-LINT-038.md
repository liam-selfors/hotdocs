# AC-LINT-038

Covers: R-LINT-004
Kind: generated-test

```gherkin
Given architecture docs arch-a depending on arch-b, arch-b depending on
  arch-a, and arch-c depending on arch-a
When lint(None, repo_root) runs
Then there is exactly one R-LINT-004 fail finding among architecture
  docs, and its message names arch-a and arch-b but not arch-c

Given only arch-c depending on arch-a, and arch-a depending on nothing
When lint(None, repo_root) runs
Then there is no R-LINT-004 finding
```
