# AC-IMPACT-007

Covers: R-IMPACT-007
Kind: compiled

```gherkin
Given a corpus containing a dangling depends_on reference unrelated to the
  changed ids
When hotdocs impact --changed comp-foo runs
Then the report's precondition_error is non-null, impacted is empty, and the
  CLI exits with code 1
```
