# R-GATE-008

**R-GATE-008** — For a non-sealed, cache-miss component, MUST call
  `provenance-tracker`'s `write_attempt_record` (`R-TRACK-007`, `D19`)
  immediately after its own `generator`/`verifier-orchestrator` calls
  conclude, passing the full `GenerationResult` and, if reached, the
  full `VerificationReport` directly. Called for both outcomes, pass
  or fail — a failed attempt's full diagnostic detail is exactly what
  a developer needs to decide whether to pass `--retry-feedback` on
  the next `hotdocs generate` call, or fix the spec first.

  **Moved here from `merge-orchestrator`'s own former `R-MERGE-021`**
  (`D86`, before `D87` removed that component entirely): this
  component is the one actually making the attempt, so it is the one
  with the detail to record. This call's own success or failure MUST
  NOT alter this component's own result — it is invoked for its
  effect, not awaited as a precondition of anything.
