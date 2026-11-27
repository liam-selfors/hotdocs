# AC-REVIEW-010

Covers: R-REVIEW-004
Kind: generated-test

```gherkin
Given AC-REVIEW-009's corpus and a model stand-in that records each
  prompt and replies {"writable": true, "gaps": []}
When check(["comp-baz"], repo_root, model="mock", llm_backend=<stand-in>)
  runs
Then the prompt for AC-BAZ-001 contains "comp-baz", "AC-BAZ-001",
  "R-BAZ-001", that criterion's Then step line, R-BAZ-001's bold line,
  baz's interface line "Returns `iface_word`.", the glossary text
  "a test term", and comp-foo's interface line "Returns `dep_word`."
```
