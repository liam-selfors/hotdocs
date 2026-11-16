# `SealedCheckResult`

```json
{
  "hit": true,
  "sealed": true,
  "reason": null,
  "verification_report": { "overall": "pass" },
  "license_scan": null,
  "secret_scan": null,
  "owners": ["pipeline-team"],
  "source_hash": "sha256:...",
  "written_at": "2026-11-02T00:00:00Z"
}
```

Returned as a dict (`R-PROVCHECK-008`). `sealed` is `false` only when
`reason` is `not_sealed`, `true` otherwise. `hit` is `true` exactly when
`reason` is `null`; otherwise `reason` is one of `not_sealed`,
`manifest_missing`, `manifest_invalid`, `component_mismatch`,
`source_changed`, `owners_changed`, `verifier_changed`, or
`characterization_failed`. `verification_report`, `owners`,
`source_hash`, and `written_at` are copied from the manifest only when
`hit` is `true` (`verification_report` holds only `overall`, taken from
`characterization.overall`) and are `null` on every miss: nothing is
taken from a manifest that is not a current, passing hit, so a stale one
never feeds a readiness result. `license_scan` and
`secret_scan` are always `null`: a sealed component's readiness rests on
its characterization run alone. The shape mirrors `ProvenanceCheckResult`
so a reader of `hit` and `verification_report.overall` needs no
special case.
