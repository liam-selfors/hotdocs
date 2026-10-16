# R-PROV-006

**R-PROV-006** — `cross_model_check` MUST be populated with an explicit
  status, never a bare absence: `ran-no-divergence` / `ran-diverged` /
  `ran-second-failed` / `not-run` (toggle disabled or no second model
  configured). `not-run` is itself a value that must be written, never
  simply omitted — consistent with D10's "visible, not silent" posture for
  everything about model availability.
