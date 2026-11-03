# AC-SECRET-004b

Covers: R-SECRET-004
Kind: generated-test

```gherkin
Given gen/foo/h.py holding the line
  sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b" (a match whose
  risk_tier is "low" but which blocks the merge), VAR-COMPLIANCE-WEBHOOK-URL
  configured, and urllib.request.urlopen replaced by a recorder
When secret-scan runs
Then flagged is true, the match's risk_tier is "low", and the
  recorder was called once, because the match blocked the merge —
  independent of its low risk_tier
```
