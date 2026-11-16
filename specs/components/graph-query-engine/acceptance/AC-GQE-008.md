# AC-GQE-008

Covers: R-GQE-008
Kind: generated-test

```gherkin
Given a repo root with a decision whose last_ratified_commit is set
  and a decision with no last_ratified_commit field at all
When load_views runs and decision_lineage is queried
Then the first row's last_ratified_commit is that commit, the second
  row's is NULL, not an empty string, and the view has no other columns
  than id and last_ratified_commit
```
