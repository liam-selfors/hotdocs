# R-TRACK-007

**R-TRACK-007** — MUST expose `write_attempt_record`, writing one
  `AttemptRecord` per component per `hotdocs generate` attempt to
  `.hotdocs/attempts/<component_id>/` — the full `GenerationResult` and,
  if generation reached it, the full `VerificationReport`, taken as
  direct parameters from `component-gate-runner`.

  Written for both outcomes, success and failure — `D19` closes a real
  gap: a failed attempt commits no provenance at all, so without this,
  its full diagnostic detail (why, not just that) would exist only in
  `component-gate-runner`'s process memory for the duration of one
  `generate` run, then vanish. `AttemptRecord` is the full-detail
  companion a human (or `provenance-tracker-ui`, `D88`) reads when a
  component's provenance check fails and they need to know why.
