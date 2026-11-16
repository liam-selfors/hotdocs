# AC-SECRET-011

Covers: R-SECRET-004
Kind: generated-test

```gherkin
Given a match whose risk_tier is high and VAR-COMPLIANCE-WEBHOOK-URL is
  configured, but the webhook call itself raises a network error
When the scan completes
Then notified is true, notification_delivery_error is populated with
  category "network", and flagged is unaffected by this failure
```

```gherkin
Given the same match, but urllib.request.urlopen raises an HTTPError
  with code 401
When the scan completes
Then notification_delivery_error's category is "auth"

Given urllib.request.urlopen instead raises socket.timeout
When the scan completes
Then notification_delivery_error's category is "timeout"

Given urllib.request.urlopen instead raises an HTTPError with code 500
When the scan completes
Then notification_delivery_error's category is "network"
```
