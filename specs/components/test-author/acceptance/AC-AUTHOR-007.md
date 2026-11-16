# AC-AUTHOR-007

Covers: R-AUTHOR-007
Kind: generated-test

```gherkin
Given a mock model that raises a network error
When author_test is called
Then the resulting TestAuthoringResult has a non-null model_call_error, a
  null file, and cache_hit is false
```
