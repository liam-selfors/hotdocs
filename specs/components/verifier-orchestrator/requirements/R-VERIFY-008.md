# R-VERIFY-008

**R-VERIFY-008** — Given the same `gen/<component>/` content, the same
  `acceptance/` content, and a judge callable that itself returns
  consistent results, this component's own orchestration logic MUST be
  idempotent — re-running it MUST reproduce the same `VerificationReport`.
  This is a claim about this component's *own* determinism, not a claim
  that `llm-judge` evaluations are reproducible in general (they may not
  be, which is exactly why this requirement is phrased conditionally on
  the judge callable's own consistency, not as a blanket idempotency
  claim).
