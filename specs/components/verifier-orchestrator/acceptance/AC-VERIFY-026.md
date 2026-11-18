# AC-VERIFY-026

Covers: R-VERIFY-006
Kind: generated-test

```gherkin
Given an unsealed comp-qux whose gen/qux/qux.py is only
  def script(): return "function cmp(a, b) { return a === b && true; }"
  and one cached generated test asserting qux.script() equals exactly
  that text
When verify runs
Then that criterion is pass and mutation_score is 1.0, from three
  mutants: === to !==, && to ||, and true to false

Given the same component and one cached generated test asserting only
  that "function" is in qux.script()
When verify runs
Then that criterion is pass, mutation_score is 0.0 and overall is
  "fail"
```
