# AC-VERIFY-012

Covers: R-VERIFY-003
Kind: compiled

```gherkin
Given a component with one llm-judge-kind acceptance criterion and a mock
  judge callable that records how many times it was called
When verify runs with that judge configured
Then the mock judge was called exactly once for that criterion — never
  zero times (it was configured) and never more than once (no
  disagreement-style second call)
```
