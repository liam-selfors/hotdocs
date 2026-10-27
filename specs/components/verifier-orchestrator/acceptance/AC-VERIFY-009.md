# AC-VERIFY-009

Covers: R-VERIFY-009
Kind: generated-test

```gherkin
Given a component with one generated-test-kind criterion and no cached test
  for it, and a mock test_author
When verify runs
Then test_author is invoked with exactly the CriterionBundle for that
  criterion, and the returned test code is executed to produce that
  criterion's result
```
