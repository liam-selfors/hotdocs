# AC-ASSIST-004

Covers: R-ASSIST-004
Kind: generated-test

```gherkin
Given a repo_root whose component foo has R-FOO-001 (text containing
  "MUST return 2 * x") covered by AC-FOO-001 (text containing
  "Then it returns 4") and R-FOO-002 with no covering criterion, stand-ins
  for all four dependencies, and an llm-endpoint stand-in that records
  each prompt and replies {"completeness_score": 0.5,
  "completeness_rationale": "R-FOO-002 untested"}
When assist(["comp-foo"], repo_root, model="fake-model") runs
Then the first recorded prompt contains "MUST return 2 * x",
  "Then it returns 4" and "No acceptance criterion covers R-FOO-002.",
  completeness_score is 0.5, and completeness_rationale is
  "R-FOO-002 untested"
```
