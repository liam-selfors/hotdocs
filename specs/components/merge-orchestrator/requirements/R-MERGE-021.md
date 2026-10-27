# R-MERGE-021

**R-MERGE-021** — For every non-sealed, cache-miss component, MUST call
  `merge-tracker`'s `write_attempt_record` (`R-TRACK-007`, `D19`)
  immediately after that component's `generator` call — and
  `verifier-orchestrator` call, if generation produced a candidate to
  verify — concludes, passing both results directly, before evaluating
  `R-MERGE-011`'s block decision. Called for every outcome, pass or
  fail, same as `R-MERGE-019`'s "both outcomes get recorded" posture for
  the end-of-merge `TrackingRecord`.

  This is what makes `D3`'s human-gated recovery path actually usable:
  a human deciding whether a blocked component's failure looks
  transient or spec-genuine needs the full `GenerationResult`/
  `VerificationReport` detail, not just the block reason `R-MERGE-006`
  records. Per `R-TRACK-005`, this call's own success or failure MUST
  NOT alter the merge's outcome, same as `R-MERGE-019`'s existing call.
