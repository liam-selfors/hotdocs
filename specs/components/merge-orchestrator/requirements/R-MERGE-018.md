# R-MERGE-018

**R-MERGE-018** — Re-running a blocked merge against an updated spec state
  MUST be a complete, correct recovery path on its own — no dedicated
  "resume" or "retry" feature is required, and none exists. This follows
  from requirements already in place, stated here explicitly so it is
  relied upon, not merely an accidental property: `generator` never writes
  to cache except on success (R-GEN-006), and a blocked merge commits
  nothing (R-MERGE-012, atomic on success only). A component whose
  `spec_bundle_hash` is unchanged since the blocked attempt is therefore a
  cache hit on re-run — not re-attempted, no repeated model-call cost — and
  a component the user edited to fix a failure is a cache miss, attempted
  fresh. R-MERGE-017's "every component to completion" is what makes this
  informative: a human fixing one failing component out of several knows,
  from the blocked attempt's own `MergeResult`, exactly which ones already
  passed and don't need attention.

  Rationale: `specs/decisions/D8.md` (the same "rollback is a cache
  hit, not a dedicated incident feature" posture the original brainstorm
  established for reverts, applied here to moving forward through
  partial failure rather than backward).
