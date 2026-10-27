# `TrackingRecord`

```json
{
  "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
  "timestamp": "2026-10-25T14:32:01Z",
  "changed_ids": ["R-FOO-003"],
  "overall": "blocked",
  "block_reasons": ["comp-bar: exhausted retries"],
  "components": {
    "comp-foo": {
      "provenance_hit": false,
      "attempts": 1,
      "model_call_error": false,
      "verification_overall": "pass",
      "license_flagged": false,
      "secret_flagged": false
    },
    "comp-bar": {
      "provenance_hit": false,
      "attempts": 2,
      "model_call_error": false,
      "verification_overall": "fail",
      "license_flagged": false,
      "secret_flagged": false
    }
  }
}
```

One file per record, filename-prefixed with `attempt_id` (R-TRACK-003) so
glob ordering is chronological. `model_call_error: true` means the final
attempt never reached verification (mirrors `ComponentPipelineResult`'s
own `model_call_error`/`verification` split, `component-gate-runner`'s
`R-GATE-004`) — in
that case `verification_overall` is `null`, not `"fail"`; those are
different facts (never produced a candidate, vs. produced one and failed
checking it). `license_flagged`/`secret_flagged` are booleans, not the
full scan result — the full `LicenseScanResult`/`SecretScanResult` lives
in `provenance-writer`'s own output; this is a summary for aggregate
querying, not a second copy of the detail (`R-TRACK-002`).
