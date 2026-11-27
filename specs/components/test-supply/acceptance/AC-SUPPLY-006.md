# AC-SUPPLY-006

Covers: R-SUPPLY-003
Kind: generated-test

```gherkin
Given the probe stand-in planted as a package,
  <repo_root>/gen/test-probe/test_probe/__init__.py, with the same
  behaviour as testing.md's file stand-in, and a current committed test
When supply("comp-foo", "AC-FOO-001", repo_root) is called
Then probe.log has one line, path is the committed file and
  failure_origin is None
```
