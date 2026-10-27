# AC-MERGE-019

Covers: R-MERGE-018
Kind: generated-test

```gherkin
Given a blocked merge attempt where component A succeeded and component
  B's one attempt failed, and the spec state is then edited so only B's
  spec_bundle_hash changes
When run_merge is called again against the updated spec state
Then generator makes no fresh model call for A (cache hit on its
  unchanged key) though verifier-orchestrator still re-confirms its
  pass, and generator makes a fresh model call for B (cache miss) — no
  distinct "retry" code path runs, this is the same run_merge call as
  any other
```
