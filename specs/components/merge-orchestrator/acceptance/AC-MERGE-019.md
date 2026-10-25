# AC-MERGE-019

Covers: R-MERGE-018
Kind: compiled

```gherkin
Given a blocked merge attempt where component A succeeded and component
  B exhausted best_of_k, and the spec state is then edited so only B's
  spec_bundle_hash changes
When run_merge is called again against the updated spec state
Then generator is not invoked for A (cache hit on its unchanged
  spec_bundle_hash) and is invoked for B (cache miss) — no distinct
  "retry" code path runs, this is the same run_merge call as any other
```
