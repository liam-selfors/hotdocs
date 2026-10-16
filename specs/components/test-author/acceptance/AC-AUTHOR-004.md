# AC-AUTHOR-004

Covers: R-AUTHOR-004
Kind: generated-test

```gherkin
Given a cache-manager pre-populated with a result for a given criterion
  content hash and model
When author_test is called with matching inputs
Then the cached result is returned and the mock model is never called
```
