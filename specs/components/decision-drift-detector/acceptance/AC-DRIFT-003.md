# AC-DRIFT-003

Covers: R-DRIFT-003
Kind: generated-test

```gherkin
Given a decision superseded by a second, and a live spec file citing
  the first, committed before the superseding decision existed
When find_decision_impact runs for the first decision's id
Then dependent_decisions contains the second decision's id, and
  citing_files contains the live spec file -- regardless of whether
  that citation would also appear in find_decision_drift's own report
```
