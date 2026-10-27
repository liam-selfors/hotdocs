# R-GATE-004

**R-GATE-004** — If the one generation attempt (`R-GATE-003`, `D3`)
  does not produce a passing candidate, this component's own result for
  that component MUST be blocked — never silently accepted. The block
  reason MUST distinguish whether the attempt never produced a
  candidate at all (`model_call_error`) from whether it produced one
  that failed verification — different facts for a human deciding, from
  `D19`'s per-attempt record, whether this looks like a transient
  failure worth a plain re-run or a genuine spec gap worth fixing
  first. `merge-orchestrator` reads this result to decide the overall
  merge block (`R-MERGE-011`); this component does not decide that
  itself.
