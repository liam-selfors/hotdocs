# AC-MERGE-017

Covers: R-MERGE-016
Kind: compiled

```gherkin
Given a component whose component.md frontmatter has no best_of_k field
When run_merge sequences its retry loop
Then at most 2 generator calls occur for that component

Given a second component whose component.md frontmatter has best_of_k: 4
When run_merge sequences its retry loop
Then up to 4 generator calls occur for that component
```
