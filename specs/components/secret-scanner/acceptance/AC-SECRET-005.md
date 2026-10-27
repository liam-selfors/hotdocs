# AC-SECRET-005

Covers: R-SECRET-005
Kind: generated-test

```gherkin
Given cache-manager already holds a result for the exact full-scan cache key
When a full scan runs with matching inputs
Then the cached result is returned and no rescan is performed
```
