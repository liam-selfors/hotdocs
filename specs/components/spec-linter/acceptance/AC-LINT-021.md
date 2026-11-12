# AC-LINT-021

Covers: R-LINT-021
Kind: generated-test

```gherkin
Given comp-foo has requirement R-FOO-001 and no acceptance file whose
  Covers: tag names it, and comp-bar has exactly one requirement,
  R-BAR-001, covered by AC-BAR-001, and a second criterion AC-BAR-002
  whose Covers: tag names R-BAR-999, which does not exist
When the linter runs
Then its only R-LINT-008 and R-LINT-009 findings are a fail-severity
  R-LINT-008 for R-FOO-001 (zero covering edges in the edges view) and
  a fail-severity R-LINT-009 for AC-BAR-002 (target not found among
  requirement nodes), both resolved via nodes/edges, not
  independently-written traversal
```
