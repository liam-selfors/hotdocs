# AC-GEN-004

Covers: R-GEN-004
Kind: generated-test

```gherkin
Given the same SpecBundle and two different model identifiers
When generate is called once with each
Then the mock model recorded for each call receives the model identifier
  passed to that call, not a hardcoded default
```
