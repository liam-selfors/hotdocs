# AC-DRIFT-001

Covers: R-DRIFT-001
Kind: generated-test

```gherkin
Given a synthetic git repo with a spec file committed citing D17,
  then (in a later commit) D17 marked deprecated with supersedes
  pointing a new D31 record ratified in that later commit
When find_decision_drift runs
Then the report's entries contains exactly one entry for that file,
  citing D17, superseded_by D31

Given D17 superseded by two later decisions, D31 and D32, each
  with the line supersedes: D17 and ratified in two different later
  commits, with D32's ratification commit a descendant of D31's
When find_decision_drift runs
Then the entry for a file citing D17 names D32 as superseded_by, the
  later-ratified of the two, never D31
```
