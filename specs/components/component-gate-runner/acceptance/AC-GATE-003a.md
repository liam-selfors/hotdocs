# AC-GATE-003a

Covers: R-GATE-003
Kind: generated-test

```gherkin
Given a mock generator/verifier-orchestrator pair where the one call's
  candidate passes verification
When run_component_gates is called
Then generator is called exactly once, and the result's verification
  shows pass with no model_call_error
```

Replaces the previous `AC-MERGE-005`, whose scenario (`k=3`, "generator
is called exactly twice") tested the best-of-k retry loop `D3` retired —
left stale rather than updated at the time, found while splitting this
component out (`D76`). `R-GATE-003` itself has always said "exactly
once"; only this acceptance criterion's scenario had drifted from it.
