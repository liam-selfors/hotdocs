# AC-MERGE-019

Covers: R-MERGE-018
Kind: generated-test

```gherkin
Given a blocked merge attempt where component A succeeded and component
  B's one attempt failed, and the spec state is then edited so only B's
  spec_bundle_hash changes
When run_merge is called again against the updated spec state
Then A's component-gate-runner call reports a provenance hit (no fresh
  model call, though its own internal verifier-orchestrator dispatch
  still re-confirms the pass), and B's component-gate-runner call
  reports a provenance miss and a fresh attempt — no distinct "retry"
  code path runs, this is the same run_merge call as any other
```
