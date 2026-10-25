# AC-SECRET-010

Covers: R-SECRET-001
Kind: generated-test

```gherkin
Given a file containing a string with entropy just above 4.0 bits/char
  and no pattern-database shape match, and a second file containing a
  string with entropy just below 4.0 bits/char
When a full secret-scan runs
Then only the first file is reported in matches, with risk_tier "low" —
  confirming the entropy threshold is exactly 4.0 bits/char, not a nearby
  value
```
