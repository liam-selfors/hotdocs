# AC-LICENSE-005

Covers: R-LICENSE-005
Kind: generated-test

```gherkin
Given a cached result under gate_version "license_scanner@1.0.0" and the
  reference corpus is updated to "license_scanner@2.0.0"
When license-scan runs with the new gate_version
Then the stale cache entry is not reused and a fresh scan is performed
```
