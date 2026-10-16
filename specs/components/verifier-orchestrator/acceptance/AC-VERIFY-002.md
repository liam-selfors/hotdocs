# AC-VERIFY-002

Covers: R-VERIFY-002
Kind: compiled

```gherkin
Given a component with one generated-test-kind acceptance criterion and its
  already-generated test file present in verification/<component>/
When verify runs
Then that test is executed against gen/<component>/ and its pass/fail
  result appears in the report
```
