# R-TRACK-007

**R-TRACK-007** — MUST expose `write_attempt_record`, writing one
  `AttemptRecord` per component per merge attempt to
  `.hotdocs/attempts/<component_id>/` — the full `GenerationResult` and,
  if generation reached it, the full `VerificationReport`, taken as
  direct parameters from `merge-orchestrator` (the same "caller's own
  facts, handed over directly" pattern `R-TRACK-001`'s
  `write_tracking_record` already uses, extended to per-component detail
  instead of merge-level facts).

  Written for both outcomes, success and failure — `D19` closes the gap
  `D3` opened: a blocked merge commits no provenance at all
  (`R-MERGE-012`), so without this, a failed attempt's full diagnostic
  detail (why, not just that) would exist only in `merge-orchestrator`'s
  process memory for the duration of one merge, then vanish. This is a
  **separate** store from `R-TRACK-001`'s `TrackingRecord` — not a
  change to that type's deliberately flattened shape (`R-TRACK-002`),
  which stays a per-merge summary — `AttemptRecord` is the full-detail
  companion a human reads when the summary says "blocked" and they need
  to know why.
