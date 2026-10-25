# AC-SCENARIO-003

Covers: R-SCENARIO-001
Kind: compiled

```gherkin
Given one product capability with two capability scenarios, one
  compiled-kind that passes and one llm-judge-kind that fails with a
  judge-provided rationale
When run_capability_scenarios runs for that capability
Then the report's scenarios array has two entries, each naming its own
  result — the compiled entry with no rationale field, the llm-judge
  entry with its rationale populated — confirming a capability with
  more than one scenario doesn't collapse into a single aggregate
  verdict with no way to tell which scenario produced it
```
