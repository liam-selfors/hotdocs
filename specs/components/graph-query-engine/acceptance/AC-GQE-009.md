# AC-GQE-009

Covers: R-GQE-001
Kind: compiled

```gherkin
Given a repo root with a real decisions corpus, including D31 (status
  ratified, supersedes D17) and D17 (status deprecated)
When load_views runs
Then nodes contains a row for D31 and a row for D17, both kind
  "decision", and edges contains a row (D31, D17, "supersedes")
```
