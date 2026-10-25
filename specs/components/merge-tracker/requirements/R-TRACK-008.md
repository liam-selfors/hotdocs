# R-TRACK-008

**R-TRACK-008** — MUST expose `last_requirement_failures(component_id,
  repo_root) -> list[str]`: the failing `R-id`s from the most recent
  `AttemptRecord` (`R-TRACK-007`) for that component whose `verification`
  is non-null, or an empty list if no such record exists. Pure read,
  read-only against `.hotdocs/attempts/` — this function MUST NOT be
  called by `merge-orchestrator` or any part of the merge pipeline
  itself (`R-MERGE-022` is explicit that `retry_feedback` is
  caller-supplied, never derived mid-merge); it exists solely so a
  human — or the CLI convenience built on it (`interface/cli.md`) —
  has a one-step way to see what to pass as `--retry-feedback`, without
  removing the decision to actually pass it from their hands.
