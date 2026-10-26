# `ProvenanceInputs`

```json
{
  "component_id": "comp-foo",
  "generation_result": { "...": "a GenerationResult" },
  "verification_report": null,
  "license_scan_result": { "...": "a LicenseScanResult" },
  "secret_scan_result": { "...": "a SecretScanResult" },
  "provenance_hit": false,
  "attempts": 2,
  "gate_versions": { "compiler": "1.0.0", "license_scanner": "k-gram@1.0.0" }
}
```

**Previously referenced in `library.md`/`constraints.md`/`AC-PROV-001` but
never actually defined here — a real, pre-existing gap, fixed now rather
than propagated further.** `generation_result` is always populated —
`GenerationResult`'s own `files`/`model_call_error`/`refused` fields (never
more than one populated, per that type's own contract) already carry
whether a candidate exists at all. `verification_report` is `null`
whenever `generation_result.files` is empty (nothing was ever produced to
verify) and populated otherwise — this mirrors `MergeResult`'s own
`model_call_error`/`verification` split (R-MERGE-005's closed gap), so
`provenance-writer` can write a coherent manifest for a component that
never reached verification, not only for one that did.

`license_scan_result`/`secret_scan_result` are always populated
regardless of generation outcome — both scans run unconditionally
(`R-MERGE-008`, D7/D12) and don't depend on `generation_result` having
succeeded. This bundle previously listed a `cross_model_check` field
(`CrossCheckResult` or `None`) from when `cross-model-divergence-checker`
existed; removed along with that component (the second-model scope cut) —
not re-added speculatively.
