# AC-SECRET-008

Covers: R-SECRET-008
Kind: generated-test

```gherkin
Given a set of files passed via --files, not yet committed
When hotdocs secret-scan precommit runs against them
Then matching is performed against only those files, with no cache-manager
  lookup attempted; an allowlist used here is valid (fixtures under `verification/`), sealed per AC-SECRET-014
```
