# AC-CACHE-001

Covers: R-CACHE-001
Kind: compiled

```gherkin
Given no entry stored for a given cache key
When get is called with that key
Then it returns Miss, not an error and not a partial result
```
