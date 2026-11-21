# AC-REVIEW-001

Covers: R-REVIEW-001
Kind: generated-test

```gherkin
Given a lint-clean synthetic corpus whose component foo has AC-FOO-001
  and AC-FOO-002
When check(["comp-foo", "AC-FOO-001"], repo_root) is called
Then criteria_checked is ["AC-FOO-001", "AC-FOO-002"]

Given the same corpus
When check(["AC-FOO-009"], repo_root) is called, and separately
  check(["comp-nothing"], repo_root) is called
Then each raises ValueError
```
