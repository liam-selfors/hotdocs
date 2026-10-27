# R-TRACK-004

**R-TRACK-004** — This component MUST NOT read or depend on
  `component-gate-runner`'s own result type. `write_attempt_record`
  MUST receive `generation_result`/`verification_report` as plain-value
  parameters, handed over directly by the caller, never as a reference
  to a `component-gate-runner`-owned type.

  **This is what keeps the dependency graph acyclic:** `component-gate-runner`
  depends on this component (it calls `write_attempt_record`); if this
  component also depended on `component-gate-runner`'s own result type,
  that would be a two-node cycle, which `spec-linter`'s `R-LINT-004`
  would correctly reject. `review-packet-builder` already established
  the precedent this requirement follows — needing some of a caller's
  facts without depending on the caller's own type, by receiving them
  as plain parameters instead.
