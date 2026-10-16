# AC-SECRET-003

Covers: R-SECRET-003
Kind: compiled

```gherkin
Given a full scan with zero matches
When secret-scan completes
Then a SecretScanResult recording the clean outcome is still written to the
  provenance manifest
```
