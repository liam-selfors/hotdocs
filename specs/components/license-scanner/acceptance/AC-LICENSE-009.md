# AC-LICENSE-009

Covers: R-LICENSE-003
Kind: compiled

```gherkin
Given a match whose risk_tier is high and VAR-COMPLIANCE-WEBHOOK-URL is
  configured, but the webhook call itself raises a network error
When the scan completes
Then notified is true, notification_delivery_error is populated with
  category "network", and blocked is unaffected by this failure
```
