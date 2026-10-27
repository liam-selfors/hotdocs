# AC-VERIFY-011

Covers: R-VERIFY-011
Kind: generated-test

```gherkin
Given a component with two criteria covering R-FOO-001 (both pass) and one
  criterion covering R-FOO-002 (fails), plus an llm-judge criterion
  covering R-FOO-003 that is skipped (no model configured)
When verify runs
Then requirement_results is {"R-FOO-001": "pass", "R-FOO-002": "fail",
  "R-FOO-003": "fail"}, and contains no Gherkin text, rationale, or
  expected/actual values anywhere in it
```
