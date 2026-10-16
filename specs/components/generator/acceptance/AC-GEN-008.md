# AC-GEN-008

Covers: R-GEN-008
Kind: generated-test

```gherkin
Given a mock model that raises a network error
When generate is called
Then the resulting GenerationResult has a non-null model_call_error, an
  empty files field, and cache_hit is false
```
