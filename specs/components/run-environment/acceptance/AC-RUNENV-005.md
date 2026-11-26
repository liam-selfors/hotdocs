# AC-RUNENV-005

Covers: R-RUNENV-005
Kind: generated-test

```gherkin
Given the fake kind declared, its provision raising RuntimeError("boom")
When prepare("comp-foo", repo_root) is called
Then it returns with ok false and failure_message
  "fake adapter failed: RuntimeError: boom"

Given no specs/components/foo/component.md at all
When prepare("comp-foo", repo_root) is called
Then ok is true and assets holds the python entry alone, and drivers
  is []
```
