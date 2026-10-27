# AC-GQE-008

Covers: R-GQE-008
Kind: generated-test

```gherkin
Given a repo root with a real decisions corpus, including one decision
  with supersedes set to a prior, now-deprecated decision
When load_views runs and decision_lineage is queried
Then the superseding row's supersedes column matches the prior
  decision's id, and the prior decision's own row has status
  "deprecated"

Given a decision with no supersedes field at all
When decision_lineage is queried
Then that row's supersedes column is NULL, not an empty string
```
