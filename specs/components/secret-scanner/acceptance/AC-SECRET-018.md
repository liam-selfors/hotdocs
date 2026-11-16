# AC-SECRET-018

Covers: R-SECRET-012
Kind: generated-test

```gherkin
Given verification/foo/t.py holding K = "AKIAABCDEFGHIJKLMNOP", a valid
  allowlist entry for it, and a ratified D1 sealing the file as in AC-SECRET-014
When scan runs
Then the finding is allowed and the result is not flagged

Given the file changed by one byte, or D1's hash changed, or D1 not
  ratified, or no decision, or a ratified D2 holding another hash
When scan runs each time
Then every finding is reported and an allowlist-invalid match is added

Given an allowlist with zero entries and no decision
When scan runs
Then no allowlist-invalid match is added
```
