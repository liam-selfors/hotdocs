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
  "review_packet": { "...": "a ReviewPacket" },
  "block_reasons": []
}
```

`attempts` is the number of generation samples actually tried for that
component before either passing or exhausting `k` (R-MERGE-005/006).
