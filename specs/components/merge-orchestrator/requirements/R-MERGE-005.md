# R-MERGE-005

**R-MERGE-005** — MUST call `generator` **exactly once** per cache-miss,
  non-sealed component per merge attempt — no automatic retry loop
  (superseded `D3`/`D17`'s best-of-k mechanism; see `specs/decisions/
  D31.md`). If that one call does not produce a passing candidate —
  either because `generator` itself returned `model_call_error`
  (R-GEN-008, no candidate was ever produced to verify) or because a
  candidate was produced but `verifier-orchestrator`'s verdict on it was
  `fail` — the component is blocked (R-MERGE-006) for this merge attempt,
  full stop. Nothing here re-calls `generator` a second time within the
  same merge. That one call MAY carry `retry_feedback` for that
  component (`R-MERGE-022`, `D33`) — but only if the caller invoking
  this merge explicitly supplied it; this component never derives or
  decides to include it on its own.

  Rationale for removing the automatic loop while keeping the recovery
  path itself free: `specs/decisions/D31.md`. Rationale for restoring
  `retry_feedback` as a caller-supplied, not automatic, input:
  `specs/decisions/D33.md`.
