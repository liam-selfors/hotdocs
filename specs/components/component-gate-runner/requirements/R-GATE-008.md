# R-GATE-008

**R-GATE-008** — For a non-sealed, cache-miss component, MUST call
  `provenance-tracker`'s `write_attempt_record` (`R-TRACK-004`, `D19`)
  immediately after its own `generator`/`verifier-orchestrator` calls
  conclude, passing the full `GenerationResult` and, if reached, the
  full `VerificationReport` directly. Called for both outcomes, pass
  or fail — a failed attempt's full diagnostic detail is exactly what
  a developer needs to decide whether to pass `--retry-feedback` on
  the next `hotdocs generate` call, or fix the spec first.

  **Moved here from `merge-orchestrator`'s own former `R-MERGE-021`**
  (`D86`, before `D87` removed that component entirely): this
  component is the one actually making the attempt, so it is the one
  with the detail to record. `D92` briefly had this component write
  the `AttemptRecord` file directly, to break a dependency cycle
  `hotdocs build` would otherwise have created; `D93` restored the
  call-based design, since `provenance-tracker` no longer calls this
  component for anything and the cycle no longer exists. This call's
  own success or failure MUST NOT alter this component's own result —
  it is invoked for its effect, not awaited as a precondition of
  anything.
