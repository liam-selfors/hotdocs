# `MergeResult`

```json
{
  "blocked": false,
  "components": {
    "comp-foo": {
      "cache_hit": false,
      "model_call_error": null,
      "verification": { "...": "a VerificationReport" },
      "license_scan": { "...": "a LicenseScanResult" },
      "secret_scan": { "...": "a SecretScanResult" }
    }
  },
  "capability_scenarios": {
    "P-ZERO-EDIT": {
      "overall": "pass",
      "scenarios": [{ "id": "CS-ZERO-EDIT-001", "kind": "generated-test", "result": "pass" }]
    }
  },
  "review_packet": { "...": "a ReviewPacket" },
  "block_reasons": []
}
```

No `attempts`/`sample_index` fields — `D31` retired the best-of-k retry
loop that gave either one a meaning beyond "always 1"/"always 0."
`model_call_error` and `verification` are **not both populated** — a
component whose one attempt never produced a candidate
(`model_call_error`) has `verification` stay `null`; a component whose
one attempt reached verification has `verification` populated (pass or
fail) and `model_call_error` stays `null`. `capability_scenarios`
(R-MERGE-014) is `capability-scenario-verifier`'s
`CapabilityScenarioReport` return value, passed through unchanged —
keyed by `P-id`, covering every capability whose `realizes`-set
intersects this merge's blast radius — a distinct result category from
`components`, never merged into any single component's own entry (per
`constraints.md`'s "never conflated" rule).
