# R-XMODEL-001

**R-XMODEL-001** — This component MUST only be invoked when at least one
  of `cross_model_divergence_check` or `fallback_standby_build` resolves to
  `enabled` and a second model is configured; if invoked anyway with neither
  condition true, it MUST report "not applicable" rather than silently
  running one of the two modes.
