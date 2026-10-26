# AC-GQE-001

Covers: R-GQE-001
Kind: compiled

```gherkin
Given a repo root with a real spec corpus
When load_views runs and nodes is queried
Then the row count per kind matches an independent file-system count
  for every one of the seven kinds
```
