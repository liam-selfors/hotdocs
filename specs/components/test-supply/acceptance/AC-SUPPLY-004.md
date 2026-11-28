# AC-SUPPLY-004

Covers: R-SUPPLY-004
Kind: generated-test

```gherkin
Given a committed test
When discard("comp-foo", "AC-FOO-001", repo_root) is called, then
  again
Then the file no longer exists and the second call raises nothing
```
