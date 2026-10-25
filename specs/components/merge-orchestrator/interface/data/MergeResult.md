# `MergeResult`

```json
{
  "blocked": false,
  "components": {
    "comp-foo": {
      "cache_hit": false,
      "attempts": 1,
      "sample_index": 0,
      "model_call_error": null,
      "verification": { "...": "a VerificationReport" },
      "license_scan": { "...": "a LicenseScanResult" },
      "secret_scan": { "...": "a SecretScanResult" }
    }
  },
  "golden_scenarios": {
    "P-ZERO-EDIT": { "result": "pass", "scenarios": ["GS-ZERO-EDIT-001"] }
  },
  "review_packet": { "...": "a ReviewPacket" },
  "block_reasons": []
}
```

`attempts` is the number of generation samples actually tried for that
component before either passing or exhausting `k` (R-MERGE-005/006).
`model_call_error` and `verification` are **not both populated** — a
component that exhausted `k` entirely via `model_call_error` (R-MERGE-005's
closed gap) never produced a candidate, so `verification` stays `null` for
it; a component where at least one attempt reached verification has
`verification` populated (pass or fail) and `model_call_error` stays
`null`, even if an earlier attempt in the same sequence *did* hit a
`model_call_error` before a later attempt succeeded or failed — this field
reports the *last* attempt's outcome, which is the one that actually
determined the component's final status. `golden_scenarios` (R-MERGE-014) is
`golden-scenario-verifier`'s `GoldenScenarioReport` return value, passed
through unchanged — keyed by `P-id`, covering every capability whose
`realizes`-set intersects this merge's blast radius — a distinct result
category from `components`, never merged into any single component's own
entry (per `constraints.md`'s "never conflated" rule).
