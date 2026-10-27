# R-GATE-003

**R-GATE-003** — MUST call `generator` **exactly once** per cache-miss,
  non-sealed component per invocation — no automatic retry loop
  (superseded the earlier design's best-of-k mechanism; see
  `specs/decisions/D3.md`). If that one call does not produce a passing
  candidate — either because `generator` itself returned
  `model_call_error` (`R-GEN-008`, no candidate was ever produced to
  verify) or because a candidate was produced but
  `verifier-orchestrator`'s verdict on it was `fail` — the component is
  blocked (`R-GATE-004`) for this attempt, full stop. Nothing here
  re-calls `generator` a second time. That one call MAY carry
  `retry_feedback` for this component (`D3`) — but only if the
  developer invoking `hotdocs generate` supplied `--retry-feedback`
  (`D86`); this component never derives or decides to include it on
  its own.

  Rationale for removing the automatic loop while keeping the recovery
  path itself free, and for restoring `retry_feedback` as a
  caller-supplied, not automatic, input: `specs/decisions/D3.md`.
