# AC-SECRET-012

Covers: R-SECRET-010
Kind: generated-test

```gherkin
Given VAR-SECRET-PATTERNS-PATH pointing at a pattern database
  (interface/data/PatternDatabase.md) whose version is "7"
When gate_version(repo_root) and scan(repo_root) are both called
Then gate_version returns the same string as the scan result's
  gate_version

Given the database's version changed to "8"
When gate_version(repo_root) is called again
Then it returns a different string than before

Given VAR-SECRET-PATTERNS-PATH unset
When gate_version(repo_root) and scan(repo_root) are both called
Then both report the same gate_version

Given a faked cache-manager that records every call
When gate_version(repo_root) is called
Then it returns a string and the faked cache-manager was never called
```
