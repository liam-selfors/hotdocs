# AC-DRIFT-002

Covers: R-DRIFT-002
Kind: generated-test

```gherkin
Given a synthetic git repo with D17 marked deprecated and superseded
  by D31 in an early commit, and a spec file citing D17 committed
  afterward (its own last-touch commit is a descendant of D31's
  ratification, not an ancestor)
When find_decision_drift runs
Then the report's entries does not contain an entry for that file --
  it was already written after the supersession, so it is not stale
```
