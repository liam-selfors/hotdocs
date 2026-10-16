# AC-CACHE-003

Covers: R-CACHE-003
Kind: compiled

```gherkin
Given two concurrent put calls for the same cache key with identical result
  payloads (the precondition G-CACHE-001 requires)
When both complete
Then a subsequent get for that key returns a result equal to both payloads,
  with no corruption or partial write — the guarantee G-CACHE-001 declares
```
