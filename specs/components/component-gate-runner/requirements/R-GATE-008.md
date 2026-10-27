# R-GATE-008

**R-GATE-008** — For a non-sealed, cache-miss component, MUST write one
  `AttemptRecord` (`provenance-tracker`'s own documented data shape,
  `interface/data/AttemptRecord.md`) directly to
  `.hotdocs/attempts/<component_id>/`, `attempt_id`-prefixed for
  chronological glob ordering, immediately after its own
  `generator`/`verifier-orchestrator` calls conclude — the full
  `GenerationResult` and, if reached, the full `VerificationReport`.
  Called for both outcomes, pass or fail — a failed attempt's full
  diagnostic detail is exactly what a developer needs to decide
  whether to pass `--retry-feedback` on the next `hotdocs build` call,
  or fix the spec first.

  **Writes the file directly — never calls into `provenance-tracker`'s
  own code to do it** (`D92`, revising `D86`'s original "calls
  `write_attempt_record`" framing): `provenance-tracker` now depends on
  this component (to trigger `hotdocs build`'s generation step), so
  this component depending back on `provenance-tracker` would be a
  two-node cycle. The file format is simple and already fully
  documented (`AttemptRecord.md`) — writing it directly costs nothing
  `write_attempt_record` was adding beyond the serialization itself.
  This call's own success or failure MUST NOT alter this component's
  own result — a failure to write the record is never a reason to
  change the generation/verification outcome itself.
