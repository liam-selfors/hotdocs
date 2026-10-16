# `MergeResult`

```json
{
  "blocked": false,
  "components": {
    "comp-foo": {
      "cache_hit": false,
      "attempts": 1,
      "sample_index": 0,
      "verification": { "...": "a VerificationReport" },
      "cross_model_check": "not-run",
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
`golden_scenarios` (R-MERGE-014) is keyed by `P-id`, covering every
capability whose `realizes`-set intersects this merge's blast radius — a
distinct result category from `components`, never merged into any single
component's own entry (per `constraints.md`'s "never conflated" rule).
