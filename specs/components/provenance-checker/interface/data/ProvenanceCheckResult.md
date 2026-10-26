# `ProvenanceCheckResult`

```json
{
  "hit": true,
  "verification_report": { "...": "a VerificationReport" },
  "license_scan": { "...": "a LicenseScanResult" },
  "secret_scan": { "...": "a SecretScanResult" }
}
```

`verification_report`/`license_scan`/`secret_scan` are populated only
when `hit` is `true` — `null` on a miss, never a partial or
best-guess value (`R-PROVCHECK-003`). On a hit, all three are the
matching `.provenance.json`'s own fields, copied verbatim — this
component never recomputes or summarizes them.
