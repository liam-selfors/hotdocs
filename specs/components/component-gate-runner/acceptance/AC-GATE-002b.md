# AC-GATE-002b

Covers: R-GATE-002
Kind: generated-test

```gherkin
Given a faked provenance-checker whose current_sealed_key returns a
  sealed key for comp-foo, a faked make_closures returning two
  sentinel callables, and a faked verify recording the judge and
  test_author it receives
When run_component_gates("comp-foo", repo_root, "m", seed=5) is called
Then make_closures received "m", 5 and repo_root, and verify received
  exactly those two sentinel callables
```
