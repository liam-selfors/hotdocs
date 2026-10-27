# AC-SCENARIO-004

Covers: R-SCENARIO-003
Kind: generated-test

```gherkin
Given one generated-test capability scenario, dispatched twice in two
  separate run_capability_scenarios calls with unchanged content
When both calls complete
Then test_author was invoked on both calls -- no cache file short-circuits
  the second dispatch
```
