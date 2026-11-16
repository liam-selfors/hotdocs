# AC-ASSIST-005

Covers: R-ASSIST-005
Kind: generated-test

```gherkin
Given a repo_root whose R-FOO-001 reads "R-FOO-001 MUST retry the upload
  three times before reporting failure", whose R-BAR-007 reads "R-BAR-007
  MUST retry the upload three times before reporting failure to the
  caller", and whose R-BAZ-001 reads "R-BAZ-001 MUST render the page in
  dark mode", stand-ins for all four dependencies, and an llm-endpoint
  stand-in that records each prompt, replying to the completeness prompt
  with a valid completeness response and to the redundancy prompt with
  {"redundancy_flags": [{"new_requirement": "R-FOO-001", "overlaps_with":
  "R-BAR-007", "rationale": "same retry rule"}, {"new_requirement":
  "R-FOO-001", "overlaps_with": "R-BAZ-001", "rationale": "x"}]}
When assist(["R-FOO-001"], repo_root, model="fake-model") runs
Then the llm-endpoint stand-in was called twice, the second prompt
  contains R-BAR-007's text and not R-BAZ-001's, and redundancy_flags is
  exactly [{"new_requirement": "R-FOO-001", "overlaps_with": "R-BAR-007",
  "rationale": "same retry rule"}]

Given the same repo_root without R-BAR-007
When assist(["R-FOO-001"], repo_root, model="fake-model") runs
Then the llm-endpoint stand-in was called once and redundancy_flags is []
```
