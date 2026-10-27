# AC-GATE-004

Covers: R-GATE-004
Kind: generated-test

```gherkin
Given a mock verifier-orchestrator that returns fail for the one
  candidate generator produced
When run_component_gates is called
Then the result is blocked with a reason indicating a failed
  verification, not a model_call_error

Given a mock generator that returns model_call_error on its one call
When run_component_gates is called
Then verifier-orchestrator is never invoked, and the result is blocked
  with a reason indicating no candidate was ever produced, not a
  failed verification
```

Replaces the previous `AC-MERGE-006`, whose scenarios (`k=2`, "generator
is called exactly twice") tested the best-of-k retry loop `D3` retired —
left stale at the time, found while splitting this component out
(`D76`). The distinguishing-reason behavior itself was already correct
and unchanged; only the call-count framing was stale.
