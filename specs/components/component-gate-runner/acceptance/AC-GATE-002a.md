# AC-GATE-002a

Covers: R-GATE-002
Kind: generated-test

```gherkin
Given a cache miss for a component with one generated-test-kind
  criterion lacking a cached test, and an already-wired test_author
  callable passed into run_component_gates
When run_component_gates is called
Then verifier-orchestrator is invoked with that same callable passed
  through unchanged, not a mock or an omitted parameter
```
