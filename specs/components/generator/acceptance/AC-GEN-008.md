# AC-GEN-008

Covers: R-GEN-008
Kind: generated-test

```gherkin
Given a mock model that raises a network error
When generate is called
Then model_call_error is non-null, files is empty, and cache_hit is false

Given a mock model whose text holds no file blocks
When generate is called
Then model_call_error has category "empty_response", files is empty,
  and nothing is written or cached
```
