# `ComponentPipelineResult`

```json
{
  "component_id": "comp-foo",
  "provenance_hit": false,
  "blocked": true,
  "block_reason": "verification_failed",
  "model_call_error": null,
  "verification": { "...": "a VerificationReport" },
  "license_scan": { "...": "a LicenseScanResult" },
  "secret_scan": { "...": "a SecretScanResult" }
}
```

`provenance_hit` (`R-GATE-001`) is `true` only on a short-circuiting
hit; `verification`/`license_scan`/`secret_scan` are then copied from
the `ProvenanceCheckResult`, `blocked` is `false`, and the other fields
are `null`.

Otherwise `blocked` (`R-GATE-004`) is `true` exactly when no passing
candidate exists: `block_reason` is `"model_call_error"` when
`generator` returned one (`model_call_error` copies it, `verification`
is `null`), or `"verification_failed"` when a candidate was produced
and `verification.overall` is not `"pass"`. A passing candidate has
`blocked` `false` and `block_reason` `null`. `model_call_error` and
`verification` are never both populated.

`blocked` concerns generation and verification only.
`license_scan.blocked` and `secret_scan.flagged` are reported as-is;
whether they stop a merge is `provenance-tracker`'s readiness check,
not this component's verdict.

Returned as a dict with exactly these keys.
