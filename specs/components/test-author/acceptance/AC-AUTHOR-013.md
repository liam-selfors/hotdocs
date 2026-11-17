# AC-AUTHOR-013

Covers: R-AUTHOR-013
Kind: generated-test

```gherkin
Given a bundle for comp-widget-maker whose dependency_interfaces is {},
  and a mock model that records
  each prompt and replies with a valid marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the first recorded prompt contains the line
  "- Only a criterion that needs `realizes`-driven behavior has the fixture supply a resolvable `P-<id>`."
```
