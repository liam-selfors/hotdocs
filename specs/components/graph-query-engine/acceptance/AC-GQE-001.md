# AC-GQE-001

Covers: R-GQE-001
Kind: generated-test

```gherkin
Given a repo root with a real spec corpus
When load_views runs and nodes is queried
Then the row count per kind matches an independent file-system count
  for every one of the seven kinds, never counting the README.md in
  specs/product/, specs/vars/ or specs/decisions/ (no other directory of
  the corpus holds one)
```
