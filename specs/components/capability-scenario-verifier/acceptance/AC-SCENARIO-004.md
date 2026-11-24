# AC-SCENARIO-004

Covers: R-SCENARIO-003
Kind: generated-test

```gherkin
Given one generated-test scenario, run in two separate
  run_capability_scenarios calls with unchanged content
When both calls complete
Then the fake test_author was invoked on both calls — nothing
  short-circuits the second dispatch

Given a fake test_author that records the bundle it receives
When a scenario is dispatched
Then the bundle's keys are exactly capability_id, scenario_id, covers,
  kind, gherkin, and file

Given a generated-test scenario and no test_author supplied
When run_capability_scenarios runs
Then that scenario's result is "fail"
```
