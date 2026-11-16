# AC-SCENARIO-003

Covers: R-SCENARIO-001
Kind: generated-test

```gherkin
Given one capability with two scenarios: a generated-test one whose
  fake test_author returns a passing test, and an llm-judge one whose
  fake judge returns {"result": "fail", "rationale": "because"}
When run_capability_scenarios runs for it
Then scenarios has two entries; the generated-test entry has no
  rationale field, the llm-judge entry has rationale "because", and
  overall is "fail"

Given a capability whose file declares no ### CS- scenario
When run_capability_scenarios runs for it
Then its overall is "fail" and its scenarios list is empty

Given a capability whose only scenario is llm-judge and no judge is
  supplied
When run_capability_scenarios runs for it
Then that entry's result is "skipped" and overall is "skipped"
```
