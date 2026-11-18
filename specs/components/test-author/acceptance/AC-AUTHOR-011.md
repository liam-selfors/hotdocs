# AC-AUTHOR-011

Covers: R-AUTHOR-011
Kind: generated-test

```gherkin
Given a bundle for comp-widget-maker whose dependency_interfaces is
  {"comp-zebra-quux": "zq_lookup(x: int, y: str) -> ZqResult"}, and a mock model that records
  each prompt and replies with a valid marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the first recorded prompt contains "comp-zebra-quux", contains
  "zq_lookup(x: int, y: str) -> ZqResult", and contains
  "a fake MUST return every field, never a bare list, string or number in its place"

Given the same call with dependency_interfaces {}
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the result's model_call_error is None and the first recorded
  prompt does not contain "comp-zebra-quux"
```
