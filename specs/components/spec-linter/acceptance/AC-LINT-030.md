# AC-LINT-030

Covers: R-LINT-030
Kind: generated-test

```gherkin
Given a decision record's builds_on naming a decision number with no
  corresponding specs/decisions/ file, and a second record's builds_on
  naming one of the fourteen decisions never formalized as files by
  design
When the linter runs
Then only the first gets an R-LINT-030 finding
```
