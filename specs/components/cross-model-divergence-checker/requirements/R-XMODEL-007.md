# R-XMODEL-007

**R-XMODEL-007** — In `standby-only` mode (`fallback_standby_build:
  enabled`, independent of whether `cross_model_divergence_check` is also
  enabled — D10's second regime): MUST still produce and verify the second
  candidate (R-XMODEL-002/003) but MUST NOT perform the R-XMODEL-004
  comparison — this is the cheaper path that buys the availability benefit
  without the divergence-detection cost.
