# AC-LINT-021

Covers: R-LINT-021
Kind: generated-test

```gherkin
Given comp-foo's R-FOO-001 has no acceptance file whose Covers: tag
  names it, and comp-bar's AC-BAR-002 has a Covers: tag naming a
  nonexistent R-id
When the linter runs
Then it fails R-LINT-008 for R-FOO-001 (zero covering edges in the
  edges view) and fails R-LINT-009 for AC-BAR-002's covers edge (target
  not found among requirement nodes) — both resolved via nodes/edges,
  not independently-written traversal
```
