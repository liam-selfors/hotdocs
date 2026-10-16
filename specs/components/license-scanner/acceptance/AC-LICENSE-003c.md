# AC-LICENSE-003c

Covers: R-LICENSE-003
Kind: compiled

```gherkin
Given a similarity score at or above the block threshold against a
  reference entry with risk_tier "low", but VAR-COMPLIANCE-WEBHOOK-URL not
  configured
When license-scan runs
Then blocked is true, notified is false, and the LicenseScanResult (per
  R-LICENSE-002) is still recorded regardless
```
