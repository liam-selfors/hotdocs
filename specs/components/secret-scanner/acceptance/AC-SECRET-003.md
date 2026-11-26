# AC-SECRET-003

Covers: R-SECRET-003
Kind: generated-test

```gherkin
Given a full scan with zero matches
When scan(repo_root) is called
Then it returns a SecretScanResult with flagged false and matches [],
  whose to_dict() holds both
```
