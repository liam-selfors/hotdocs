# R-MERGE-022

**R-MERGE-022** — `run_merge` MAY optionally receive `retry_feedback`: a
  mapping of `component_id` to an `R-id` list, supplied by whoever is
  invoking this merge. For a component with an entry in that mapping,
  the one `generator` call R-MERGE-005 makes for it MUST include that
  `R-id` list as `retry_feedback` (R-GEN-012); every other component's
  call MUST remain blind.

  This component MUST NOT compute, derive, or default this mapping
  itself — not from `.hotdocs/attempts/`, not from any prior merge's
  `TrackingRecord`, not from anything else on disk. The decision to
  retry *with* feedback, and the feedback's content, belongs entirely
  to the human (or script) initiating this call (`D3`) — reading
  `merge-tracker`'s `last_requirement_failures` (`R-TRACK-008`) to
  decide what to supply is something the caller does *before* calling
  `run_merge`, never something this component reaches for mid-merge.
