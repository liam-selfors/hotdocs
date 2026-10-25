# R-LICENSE-007

**R-LICENSE-007** — When a component's flagged attempt blocks a merge
  and a later merge attempt (a human re-running `hotdocs merge` after
  `D31`'s retirement of automatic retry) scans clean, the **original**
  flagged result MUST remain recorded — never overwritten or erased.
  Before `D31`, this held within one merge's own provenance manifest (a
  later best-of-k sample's clean result recorded alongside the original
  flag). A blocked merge now commits nothing at all (`R-MERGE-012`), so
  there is no manifest for the flagged attempt to live in — `D32`'s
  per-attempt record (`.hotdocs/attempts/`) is what preserves it instead.
  "Auto-resolved by retry" still means the merge is no longer blocked; it
  still does not mean the flag never happened.
