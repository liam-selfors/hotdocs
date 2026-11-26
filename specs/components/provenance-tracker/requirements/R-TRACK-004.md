# R-TRACK-004

**R-TRACK-004** — This component MUST NOT read or depend on
  `component-gate-runner`'s own result type. `write_attempt_record`
  MUST receive `generation_result`/`verification_report` as plain-value
  parameters, handed over directly by the caller, never as a reference
  to a `component-gate-runner`-owned type.

  This keeps the dependency graph acyclic: `component-gate-runner`
  depends on this component.
