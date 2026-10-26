# AC-LINT-022

Covers: R-LINT-022
Kind: compiled

```gherkin
Given a component whose generated_code_loc and component_doc_words are both
  over their warn thresholds, and a second component with only
  generated_code_loc over its warn threshold
When the linter runs
Then the first component gets a distinct R-LINT-022 warning naming both
  dimensions and SPEC_GUIDELINES.md Section 4, and the second component
  gets no R-LINT-022 finding at all — confirming the rule fires only when
  two or more dimensions crowd at once, not on a single near-miss
```
