# AC-AUTHOR-024

Covers: R-AUTHOR-024
Kind: generated-test

```gherkin
Given a bundle for comp-widget-maker whose dependency_interfaces is {},
  and a mock model that records
  each prompt and replies with a valid marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the first recorded prompt contains
  "the fake's own code appends one line per call to a log file at a path the test controls"
  and contains
  "never with `str.format`, `%` or an f-string over text that holds braces or percent signs."
```
