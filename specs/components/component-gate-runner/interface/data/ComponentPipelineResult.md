# `ComponentPipelineResult`

```json
{
  "provenance_hit": false,
  "model_call_error": null,
  "verification": { "...": "a VerificationReport" },
  "license_scan": { "...": "a LicenseScanResult" },
  "secret_scan": { "...": "a SecretScanResult" }
}
```

Unchanged in shape from the per-component entry `MergeResult.components`
already carried before `D76` — this is that same shape, now named and
owned here rather than defined inline inside `MergeResult`.
`model_call_error` and `verification` are **not both populated**: a
component whose attempt never produced a candidate has `verification`
stay `null`; one that reached verification has `verification` populated
(pass or fail) and `model_call_error` stays `null`. `provenance_hit`
(`R-GATE-001`, `D29`) is `true` only when `provenance-checker` reported
a hit, meaning the other fields are copied from a committed
`.provenance.json` rather than freshly computed. `merge-orchestrator`
collects one of these per impacted component into
`MergeResult.components`, keyed by `component_id`, unchanged.
