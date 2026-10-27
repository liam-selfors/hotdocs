# AC-VERIFY-003

Covers: R-VERIFY-003
Kind: generated-test

```gherkin
Given a component with one llm-judge-kind acceptance criterion
When verify runs with no judge configured
Then that criterion's result is skipped, with a null rationale, and verify
  does not call a model itself to produce that result
```
