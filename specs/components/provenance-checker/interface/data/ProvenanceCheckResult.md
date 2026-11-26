# `ProvenanceCheckResult`

```json
{
  "hit": true,
  "reason": null,
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

`reason` is `null` on a hit; on a miss, the first that applies, in this
order: `no manifest`, `R-PROVCHECK-011`'s `dependency code differs` or
else `spec_bundle_hash differs`, `gate_versions differ`,
then `R-PROVCHECK-009`'s `unknown asset kind: <kind>`, the adapter's
provision reason, or `R-PROVCHECK-010`'s `environment differs` or
else `assets differ`, then `llm-judge results not trusted`.
