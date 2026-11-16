# AC-VERIFY-001

Covers: R-VERIFY-001
Kind: generated-test

```gherkin
Given a component with one compiled-kind acceptance criterion and a mock
  criterion-compiler
When verify runs
Then the mock compiler is invoked for that criterion and its pass/fail
  result appears in the report under that criterion's id
```
