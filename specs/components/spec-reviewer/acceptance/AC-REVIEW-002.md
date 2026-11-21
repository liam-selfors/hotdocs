# AC-REVIEW-002

Covers: R-REVIEW-002
Kind: generated-test

```gherkin
Given a synthetic corpus whose component foo has an acceptance file with
  its Kind: line deleted (a fail-severity lint finding), and a counting
  mock llm_backend
When check(["comp-foo"], repo_root, model="mock") is called
Then lint_findings holds at least one finding with severity "fail",
  criteria_checked is empty, and the mock backend was called 0 times

Given a lint-clean synthetic corpus
When check(["comp-foo"], repo_root) is called
Then no finding in lint_findings has severity "fail" and
  criteria_checked is non-empty
```
