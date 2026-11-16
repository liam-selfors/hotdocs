# R-VERIFY-008

**R-VERIFY-008** — Given the same `gen/<component>/` content, the same
  `acceptance/` content, and a judge callable that itself returns
  consistent results, this component's own orchestration logic MUST be
  idempotent: re-running it MUST reproduce the same `VerificationReport`.
  This claims this component's *own* determinism, not that `llm-judge`
  evaluations are reproducible, hence the condition on the judge.
