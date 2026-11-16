# AC-SECRET-015

Covers: R-SECRET-012
Kind: generated-test

Setup: `AC-SECRET-014`'s first scenario (sealed again after each change), plus the change named.

```gherkin
Given the line changed to K = "AKIAZZZZYYYYXXXXWWWW"
When a full scan runs
Then flagged is true, matches holds that line, allowed is empty, and
  unused_allowlist_entries holds the entry

Given the original key also written to verification/foo/other.py
When a full scan runs
Then matches holds exactly one entry, for verification/foo/other.py,
  and allowed still holds the original

Given a second line added to test_x.py: J = "AKIAZZZZYYYYXXXXWWWW"
When a full scan runs
Then matches holds exactly the new line

Given the entry's type changed to "Hex High Entropy String"
When a full scan runs
Then flagged is true and the original finding is in matches
```
