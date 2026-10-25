# AC-MERGE-014

Covers: R-MERGE-014
Kind: compiled

```gherkin
Given every component in the blast radius has passed its own
  per-component verification
When run_merge reaches the golden-scenario step
Then golden-scenario-verifier is called with the full blast-radius id set
  and the same real judge/test_author callables wired into
  verifier-orchestrator's call, and a failing GoldenScenarioReport it
  returns blocks the overall merge independent of any component's own
  verification result
```
