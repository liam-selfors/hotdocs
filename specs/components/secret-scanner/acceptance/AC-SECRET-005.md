# AC-SECRET-005

Covers: R-SECRET-005
Kind: generated-test

```gherkin
Given cache-manager already holds a result for the exact full-scan cache key
When a full scan runs with matching inputs
Then the cached result is returned with cache_hit true and exactly
  the cached matches — even when the cached matches differ from what a
  fresh scan of the current files would find — and put is not called.
  Files are still read to compute the cache key itself; reading them is
  not a rescan
```
