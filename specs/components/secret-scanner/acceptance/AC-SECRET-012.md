# AC-SECRET-012

Covers: R-SECRET-010
Kind: generated-test

```gherkin
Given any repo_root
When gate_version(repo_root) and scan(repo_root) are both called
Then gate_version returns the same string as the scan result's
  gate_version

Given a stand-in cache-manager that records every call, and a repo_root
  holding a file with a secret in it
When gate_version(repo_root) is called
Then it returns a string, the stand-in was never called, and no file
  anywhere under repo_root was created or changed
```
