# AC-GQE-010

Covers: R-GQE-002
Kind: generated-test

```gherkin
Given a decision whose prose quotes `supersedes: D1` and
  `builds_on: [D2]` but whose frontmatter declares neither
When load_views runs and edges is queried
Then edges has no supersedes or builds_on row for that decision

Given a decision whose frontmatter declares builds_on: [D1, D2]
When edges is queried
Then it has exactly the rows (that decision, D1, builds_on) and
  (that decision, D2, builds_on)
```
