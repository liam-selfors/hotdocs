# AC-SECRET-011

Covers: R-SECRET-004
Kind: compiled

```gherkin
Given a match whose risk_tier is high and VAR-COMPLIANCE-WEBHOOK-URL is
  configured, but the webhook call itself raises a network error
When the scan completes
Then notified is true, notification_delivery_error is populated with
  category "network", and flagged is unaffected by this failure
```
