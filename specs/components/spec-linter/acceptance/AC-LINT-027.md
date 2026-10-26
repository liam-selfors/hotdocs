# AC-LINT-027

Covers: R-LINT-027
Kind: compiled

```gherkin
Given a live requirement citing a real file's "Query surface" section,
  and another citing the same file's "Nonexistent Heading" section
When the linter runs
Then only the second citation gets a R-LINT-027 finding
```
