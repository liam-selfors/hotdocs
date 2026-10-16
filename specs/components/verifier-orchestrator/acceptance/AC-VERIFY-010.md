# AC-VERIFY-010

Covers: R-VERIFY-010
Kind: compiled

```gherkin
Given a component with one generated-test-kind criterion, no cached test,
  and no test_author configured
When verify runs
Then that criterion's result is fail, not skipped, and the overall verdict
  is fail
```
