# AC-DRIFT-001

Covers: R-DRIFT-001
Kind: compiled

```gherkin
Given a synthetic git repo with a spec file committed citing D17,
  then (in a later commit) D17 marked deprecated with supersedes
  pointing a new D31 record ratified in that later commit
When find_decision_drift runs
Then the report's entries contains exactly one entry for that file,
  citing D17, superseded_by D31
```
