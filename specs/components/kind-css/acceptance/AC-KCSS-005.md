# AC-KCSS-005

Covers: R-KCSS-004
Kind: generated-test

```gherkin
Given tmp_path as repo_root
When provision(repo_root) is called twice
Then each result equals {"ok": True, "reason": "", "versions": {},
  "lockfile_sha256": None}, the two results are different objects, and
  tmp_path is still empty
```
