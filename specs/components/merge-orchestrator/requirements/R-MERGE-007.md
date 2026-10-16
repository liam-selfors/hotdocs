# R-MERGE-007

**R-MERGE-007** — MUST invoke `cross-model-divergence-checker` for each
  impacted component for which `cross_model_divergence_check` or
  `fallback_standby_build` resolves to `enabled` with a second model
  configured — and MUST NOT invoke it otherwise (R-XMODEL-001's
  precondition is enforced by never calling it, not by calling it and
  discarding the "not applicable" result).
