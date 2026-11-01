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

```gherkin
Given VAR-COMPLIANCE-WEBHOOK-URL configured, urllib.request.urlopen
  replaced by a recorder, and files with no match at all
When secret-scan runs
Then notified is false and urlopen was never called

Given VAR-COMPLIANCE-WEBHOOK-URL unset and a match against a high
  risk_tier rule
When secret-scan runs
Then flagged is true, notified is false, and urlopen was never called
```
