# R-MERGE-006

**R-MERGE-006** — If the one generation attempt (`R-MERGE-005`, `D3`)
  does not produce a passing candidate, the merge MUST be blocked for
  that component — never silently accepted. The block reason MUST
  distinguish whether the attempt never produced a candidate at all
  (`model_call_error`) from whether it produced one that failed
  verification — different facts for a human deciding, from `D19`'s
  per-attempt record, whether this looks like a transient failure worth
  a plain re-run or a genuine spec gap worth fixing first.
