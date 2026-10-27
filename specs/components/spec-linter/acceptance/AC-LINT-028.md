# AC-LINT-028

Covers: R-LINT-028
Kind: generated-test

```gherkin
Given a live requirement citing the glossary's "Component id /
  component slug" term, and another citing the glossary's
  "Nonexistent Made Up Term"
When the linter runs
Then only the second citation gets a R-LINT-028 finding
```
