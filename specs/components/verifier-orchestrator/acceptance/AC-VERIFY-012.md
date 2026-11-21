# AC-VERIFY-012

Covers: R-VERIFY-003
Kind: generated-test

```gherkin
Given a component with one llm-judge-kind criterion and a mock judge
  that counts its calls
When verify runs with that judge
Then the mock judge was called exactly once
```
