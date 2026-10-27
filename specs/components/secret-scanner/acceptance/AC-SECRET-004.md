# AC-SECRET-004

Covers: R-SECRET-004
Kind: generated-test

```gherkin
Given a match against a high-risk_tier rule (e.g. a recognizable AWS
  access-key shape) and VAR-COMPLIANCE-WEBHOOK-URL configured
When secret-scan runs
Then a notification is sent, independent of whether a later retry scans
  clean
```
