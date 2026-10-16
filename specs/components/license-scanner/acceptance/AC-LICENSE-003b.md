# AC-LICENSE-003b

Covers: R-LICENSE-003
Kind: compiled

```gherkin
Given a similarity score below the block threshold against a reference
  entry with risk_tier "high", and VAR-COMPLIANCE-WEBHOOK-URL configured
When license-scan runs
Then blocked is false but notified is true — the exact case a same-scale
  severity threshold could never express
```
