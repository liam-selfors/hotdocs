# AC-CACHE-008

Covers: R-CACHE-008
Kind: compiled

```gherkin
Given a key that was successfully put, then evicted by the backing store
  before any get for it
When get is called with that key
Then it returns a definitive miss, indistinguishable in shape from a
  backing-store error (R-CACHE-004) or a key that was simply never
  stored — the caller's handling is identical in all three cases
```
