# AC-TRACK-001

Covers: R-TRACK-001
Kind: compiled

```gherkin
Given a merge attempt that blocks, followed by a spec edit and a second
  merge attempt that passes
When both attempts complete
Then two separate tracking records exist, each with its own distinct
  attempt_id, and neither record was modified after being written
```
