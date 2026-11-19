# AC-VERIFY-026

Covers: R-VERIFY-006
Kind: generated-test

```gherkin
Given an unsealed comp-qux whose gen/qux/qux.py defines only
  qux() returning None, declaring assets: [fake:data/table.txt] with the
  fake kind of verifier-fixtures.md planted, and one cached generated
  test asserting asset_runner("data/table.txt")("a", []) == 1
When verify runs
Then that criterion is pass, mutation_score == 0.5 and overall is
  "fail"

Given the same test also asserts asset_runner("data/table.txt")("b", []) == 2
When verify runs
Then mutation_score == 1.0
```
