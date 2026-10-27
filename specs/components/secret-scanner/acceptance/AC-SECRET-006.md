# AC-SECRET-006

Covers: R-SECRET-006
Kind: generated-test

```gherkin
Given a cached result under gate_version "secret_scanner@1.0.0" and the
  pattern database is updated to "secret_scanner@2.0.0"
When a full scan runs with the new gate_version
Then the stale cache entry is not reused and a fresh scan is performed
```
