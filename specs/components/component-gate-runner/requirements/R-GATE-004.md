# R-GATE-004

**R-GATE-004** — If the loop did not pass, the result MUST be `blocked`,
  never silently accepted, with `block_reason` from the last attempt's
  `outcome`: `generation_failed` gives `"model_call_error"` (with
  `model_call_error` the last generation result's), `surface_failed`
  gives `"surface_check_failed"`, `refused` gives `"refused"`, and
  `verification_failed` gives `"test_authoring_failed"` when that
  attempt's `VerificationReport` has at least one criterion whose
  `result` is `"fail"` and every such criterion has `failure_origin`
  `"test"` (`D319`), else `"verification_failed"`.
  Overall merge readiness stays `provenance-tracker`'s decision.
