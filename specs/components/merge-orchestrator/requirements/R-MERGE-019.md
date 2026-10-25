# R-MERGE-019

**R-MERGE-019** — MUST call `merge-tracker` as the last step of every
  merge attempt, success or block, passing `changed_ids`, the full
  impacted component id set, `block_reasons`, and the overall outcome —
  after `review-packet-builder` (so `provenance-writer`'s manifests
  `merge-tracker` reads are already written) and regardless of R-MERGE-011's
  block decision (both outcomes get recorded, per `R-TRACK-001`). Per
  `R-TRACK-005`, this call's own success or failure MUST NOT alter the
  merge's outcome — it is invoked for its effect, not awaited as a
  precondition of anything.
