# AC-SECRET-016

Covers: R-SECRET-012
Kind: generated-test

Setup for each scenario: `verification/foo/test_x.py` and `gen/foo/c.py`
both holding `K = "AKIAABCDEFGHIJKLMNOP"`, an otherwise valid allowlist for
`test_x.py`, then the one corruption named. Each expects: flagged true,
**both** AWS findings in matches, and one extra match with rule_id
"allowlist-invalid", risk_tier "high", file ".secret-allowlist.json",
line 1.

```gherkin
Given the file is not valid JSON
Given a top-level key besides version and entries, or version 2
Given an entry with an extra key, or a missing key
Given an entry whose reason is "other"
Given an entry whose hashed_secret lacks the "sha1:" prefix
Given an entry whose file is "../x.py", "/etc/x", or "verification/*.py"
Given an entry with reason "planted-fixture" and file "gen/foo/c.py"
Given an entry with reason "public-constant" and type "AWS Access Key"
Given a second, otherwise valid entry beside a corrupt one
When a full scan runs
Then the expectations above hold for each

Given an extra key whose value is "AKIAZZZZYYYYXXXXWWWW"
When a full scan runs
Then, besides the above, a match for .secret-allowlist.json itself with
  rule_id "AWS Access Key" is reported: the allowlist is scanned
```

```gherkin
Given no .secret-allowlist.json at all
When a full scan runs
Then flagged is true, there is no "allowlist-invalid" match, and
  allowed is empty
```
