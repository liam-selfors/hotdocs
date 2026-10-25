# R-TRACK-001

**R-TRACK-001** — This component MUST write exactly one tracking record
  per merge attempt, regardless of whether that attempt succeeded or was
  blocked. "One attempt" means one invocation of `merge-orchestrator`'s
  `run_merge` — a merge that is retried by re-invoking `run_merge`
  (`R-MERGE-018`) produces a second, separate tracking record, not an
  update to the first; the record is append-only history, never mutated
  after being written.
