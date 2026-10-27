# AC-GQE-009

Covers: R-GQE-001
Kind: compiled

```gherkin
Given a repo root with a synthetic decisions corpus, including one
  decision record with supersedes set to a second, and the second
  record's own status set to "deprecated"
When load_views runs
Then nodes contains a row for each decision, both kind "decision", and
  edges contains a row (first, second, "supersedes")
```
