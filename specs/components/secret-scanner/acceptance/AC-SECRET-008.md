# AC-SECRET-008

Covers: R-SECRET-008
Kind: compiled

```gherkin
Given a set of files passed via --files, not yet committed
When hotdocs secret-scan precommit runs against them
Then matching is performed against only those files, with no cache-manager
  lookup attempted
```
