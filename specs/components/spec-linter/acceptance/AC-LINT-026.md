# AC-LINT-026

Covers: R-LINT-026
Kind: compiled

```gherkin
Given a live component.md citing a decision number with no
  corresponding specs/decisions/ file, and a second citing one of the
  fourteen decisions never formalized as files by design
When the linter runs
Then only the first citation gets a R-LINT-026 finding
```
