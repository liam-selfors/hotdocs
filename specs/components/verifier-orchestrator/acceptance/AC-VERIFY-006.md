# AC-VERIFY-006

Covers: R-VERIFY-006
Kind: generated-test

```gherkin
Given comp-qux whose gen/qux/qux.py defines g(a, b) returning a < b and
  h(a, b) returning a // b, with verifier-fixtures.md's assembler and
  probe stand-ins, and one current cached generated test asserting
  only qux.g(1, 2) is True and qux.g(2, 1) is False
When verify runs
Then mutation_score is 0.5, mutation_error is None, the criterion is
  "pass", and overall is "fail"
```
