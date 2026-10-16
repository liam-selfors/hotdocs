# AC-SECRET-009

Covers: R-SECRET-009
Kind: compiled

```gherkin
Given a first generation sample that scans flagged, and a retried sample
  that scans clean
When the final merge decision is made
Then both the original flagged SecretScanResult and the clean one are
  present in the record
```
