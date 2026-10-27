# AC-LICENSE-003

Covers: R-LICENSE-003
Kind: generated-test

```gherkin
Given a similarity score at or above the block threshold (so the merge is
  blocked) against a reference entry with risk_tier "low", and
  VAR-COMPLIANCE-WEBHOOK-URL configured
When license-scan runs
Then notified is true, because the match blocked the merge — independent
  of that entry's low risk_tier
```
