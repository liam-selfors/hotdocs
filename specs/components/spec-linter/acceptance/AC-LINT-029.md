# AC-LINT-029

Covers: R-LINT-029
Kind: generated-test

```gherkin
Given a decision record with supersedes: D<N> where D<N> does not exist
When the linter runs
Then that record gets an R-LINT-029 finding

Given a decision record with supersedes: D<N> where D<N> exists but is
  still status: ratified, not deprecated
When the linter runs
Then the superseding record gets an R-LINT-029 finding naming D<N>

Given a decision record with status: deprecated that no other real
  decision's supersedes field names
When the linter runs
Then that record gets an R-LINT-029 finding
```
