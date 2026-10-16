# AC-SECRET-004b

Covers: R-SECRET-004
Kind: compiled

```gherkin
Given a match against a low-risk_tier rule (a generic high-entropy
  heuristic) that nonetheless blocked the merge, and
  VAR-COMPLIANCE-WEBHOOK-URL configured
When secret-scan runs
Then a notification is still sent, because the match blocked the merge —
  independent of that rule's low risk_tier
```
