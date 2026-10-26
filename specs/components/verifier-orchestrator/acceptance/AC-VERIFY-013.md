# AC-VERIFY-013

Covers: R-VERIFY-012
Kind: compiled

```gherkin
Given a compiled criterion whose compiled assertion checks result.foo
  equals 5, and the generated code under test returns 3
When verify_component runs
Then that criterion's result is fail, its failure_detail.expected is 5,
  and its failure_detail.actual is 3
```
