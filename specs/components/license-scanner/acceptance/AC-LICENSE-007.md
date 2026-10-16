# AC-LICENSE-007

Covers: R-LICENSE-007
Kind: compiled

```gherkin
Given a first generation sample that scans flagged, and a retried sample
  that scans clean
When the final merge decision is made
Then both the original flagged LicenseScanResult and the clean one are
  present in the record — the flagged one is not deleted or overwritten
```
