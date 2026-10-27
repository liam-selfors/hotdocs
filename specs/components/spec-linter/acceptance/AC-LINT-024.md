# AC-LINT-024

Covers: R-LINT-024
Kind: generated-test

```gherkin
Given a component's Purpose section containing the text "extracted once
  D30 found a real coupling"
When the linter runs
Then it fails with R-LINT-024, and a second component whose Purpose has
  no decision citation (with that same citation moved to its own
  Rationale section instead) produces no R-LINT-024 finding
```
