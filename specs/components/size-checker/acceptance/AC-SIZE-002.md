# AC-SIZE-002

Covers: R-SIZE-002
Kind: generated-test

```gherkin
Given a component whose generated_code_loc and component_doc_words are both
  over their warn thresholds, and a second component with only
  generated_code_loc over its warn threshold
When check(repo_root) runs
Then the first component gets a distinct R-SIZE-002 warning naming both
  dimensions and SPEC_GUIDELINES.md Section 4, and the second component
  gets no R-SIZE-002 finding at all
```
