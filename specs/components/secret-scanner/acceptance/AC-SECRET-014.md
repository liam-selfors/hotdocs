# AC-SECRET-014

Covers: R-SECRET-012
Kind: generated-test

Scenarios write `.secret-allowlist.json` themselves, `hashed_secret` being
`"sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()`, and seal it
with `specs/decisions/D1.md` (`status: ratified`, `allowlist_sha256:
sha256:<hex of the file>`).

```gherkin
Given verification/foo/test_x.py holding K = "AKIAABCDEFGHIJKLMNOP" and
  an allowlist whose one entry is {file "verification/foo/test_x.py",
  type "AWS Access Key", that secret's hash, reason "planted-fixture"},
  VAR-COMPLIANCE-WEBHOOK-URL configured, and urlopen replaced by a
  recorder
When a full scan runs
Then flagged is false, matches is empty, allowed holds one entry
  {rule_id "AWS Access Key", file "verification/foo/test_x.py", line 1},
  notified is false, and the recorder was never called

Given gen/foo/g.py holding
  EMPTY = "4b825dc642cb6eb9a060e54bf8d69288fbee4904" and an entry for it
  with type "Hex High Entropy String" and reason "public-constant"
When a full scan runs
Then flagged is false and allowed holds that finding

Given a valid entry that matches no finding
When a full scan runs
Then flagged is false, allowed is empty, and unused_allowlist_entries
  holds {file, type} for that entry

Given the first scenario's files, and scan_files([<the file>],
  repo_root=<repo_root>), then scan_files([<the file>]) with no repo_root
When each runs
Then the first has flagged false and the second has flagged true
```
