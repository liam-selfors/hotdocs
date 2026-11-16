# R-GATE-004

**R-GATE-004** — If the one generation attempt does not produce a
  passing candidate, the result MUST be `blocked`, never silently
  accepted, with a `block_reason` distinguishing `"model_call_error"`
  (no candidate was ever produced, and `verifier-orchestrator` was
  never called) from `"verification_failed"` (a candidate was produced
  and failed) — different facts for a developer deciding whether to
  re-run or fix the spec first (`D19`). Overall merge readiness stays
  `provenance-tracker`'s decision.
