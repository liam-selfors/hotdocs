# R-MERGE-011

**R-MERGE-011** — The overall merge MUST be blocked if any impacted
  component exhausted retries (R-MERGE-006), or a sealed component's
  characterization-test verification (R-MERGE-015) failed, or
  `cross-model-divergence-checker` reported a blocking divergence, or
  either scanner reported a blocking flag, or golden-scenario verification
  (R-MERGE-014) failed — and MUST proceed otherwise.

  The sealed-component case is listed explicitly, not folded into
  "exhausted retries": R-MERGE-015 has no retry loop at all (retrying
  can't help — the code is hand-maintained, not regenerated), so a failed
  characterization test there has no other block condition that would
  otherwise catch it. Omitting it here would have been a real, silent gap.
