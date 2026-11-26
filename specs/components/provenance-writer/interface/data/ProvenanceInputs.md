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
  "attempt_history": [{"number": 1, "outcome": "passed", "retry_feedback": [],
                       "error_category": null, "failed_requirements": [],
                       "transcript_sha256": null}],
  "gate_versions": { "compiler": "1.0.0", "license_scanner": "k-gram@1.0.0" },
  "spec_bundle_parts": {"spec": "sha256:...", "dependency_code": "sha256:..."}
}
```

`attempt_history` is the landing run's attempts, each a plain dict with
exactly those keys (`generation-loop`'s `AttemptLoopResult`); it MAY be
absent, meaning `[]`. `spec_bundle_parts` is the provenance key's
(`provenance-checker`), and MAY be absent, meaning `null`. `generation_result` is always populated; its
`files`/`model_call_error`/`refused` fields carry whether a candidate
exists. `verification_report` is `null` whenever `generation_result.files`
is empty, except when committed code is re-verified (`D345`), and
populated otherwise; a `null` report alongside non-empty
`files` is a missing upstream result, so `write_provenance` raises
`MissingInputError` and writes no manifest. A manifest is thus written
for a component that never reached verification too.

`license_scan_result`/`secret_scan_result` are always populated: both
scans run whatever the generation outcome. Accepted shapes and required
inputs: `specs/architecture/provenance-writer-fixtures.md`.
