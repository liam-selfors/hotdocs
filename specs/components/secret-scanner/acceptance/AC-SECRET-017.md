# AC-SECRET-017

Covers: R-SECRET-013
Kind: generated-test

```gherkin
Given verification/foo/t.py holding K = "AKIAABCDEFGHIJKLMNOP",
  gen/foo/g.py holding EMPTY = "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
  and gen/foo/c.py holding C = "AKIAZZZZYYYYXXXXWWWW"
When propose(repo_root) is called
Then allowlist.entries holds exactly two entries — verification/foo/t.py
  "AWS Access Key" reason "planted-fixture", and gen/foo/g.py
  "Hex High Entropy String" reason "public-constant", each with the
  secret's "sha1:" hash — sorted by file; ineligible holds exactly
  {file "gen/foo/c.py", line 1, rule_id "AWS Access Key"}; and no
  .secret-allowlist.json was created

Given a valid, sealed allowlist already covering t.py's key
When propose(repo_root) is called
Then that entry appears once

Given an invalid allowlist
When propose(repo_root) is called
Then AllowlistInvalidError is raised

Given the first scenario's repository
When main(["propose", "--repo-root=<repo_root>"]) runs
Then it returns 1 and prints JSON with those two keys; with c.py
  removed it returns 0
```
