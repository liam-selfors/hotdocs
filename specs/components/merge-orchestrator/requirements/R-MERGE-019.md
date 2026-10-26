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

  If this call itself raises or errors, that failure MUST be caught and
  surfaced as `MergeResult.tracking_write_error` (non-blocking, the same
  structured `{category, message}` shape `model_call_error` already
  established, D32) — never silently swallowed, per the non-gating
  posture above.
