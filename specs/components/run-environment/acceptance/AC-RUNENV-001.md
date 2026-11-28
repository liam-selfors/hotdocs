# AC-RUNENV-001

Covers: R-RUNENV-001
Kind: generated-test

```gherkin
Given the fake kind declared
When prepare("comp-foo", repo_root) is called
Then ok is true, failure_message is None and interpreter is the real
  python adapter's provision(repo_root)["interpreter"]

Given the unprovisioned fake kind declared, and separately
  "assets: [nokind:x.txt]"
When prepare is called
Then ok is false and failure_message is "fake needs fakeprog >= 2",
  or "unknown asset kind: nokind"
```
