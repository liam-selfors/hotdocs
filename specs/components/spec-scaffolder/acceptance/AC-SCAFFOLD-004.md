# AC-SCAFFOLD-004

Covers: R-SCAFFOLD-004
Kind: generated-test

```gherkin
Given a git repository as repo_root in which new_decision then ratify
  produced specs/decisions/D1.md and that file has been committed
When record_commit(repo_root, "D1") is called
Then it returns the output of `git log -1 --format=%h --
  specs/decisions/D1.md`, and D1.md's line is now
  "last_ratified_commit: <that hash>"

Given that same repository after the record_commit
When record_commit(repo_root, "D1") is called again
Then it raises LookupError and D1.md is unchanged

Given a git repository in which D2.md was ratified but never committed
When record_commit(repo_root, "D2") is called
Then it raises LookupError

Given the same repository
When record_commit(repo_root, "D2", commit="abc1234") is called
Then it returns "abc1234" and D2.md's line is now
  "last_ratified_commit: abc1234"
```
