# R-GATE-004

**R-GATE-004** — If the loop did not pass, the result MUST be `blocked`,
  never silently accepted, with `block_reason` from the last attempt's
  `outcome`: `generation_failed` gives `"model_call_error"` (with
  `model_call_error` the last generation result's), `surface_failed`
  gives `"surface_check_failed"`, `verification_failed` gives
  `"verification_failed"`, and `refused` gives `"refused"`. Overall merge
  readiness stays `provenance-tracker`'s decision.
