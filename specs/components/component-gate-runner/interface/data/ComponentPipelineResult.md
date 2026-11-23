# `ComponentPipelineResult`

```json
{
  "component_id": "comp-foo",
  "provenance_hit": false,
  "reverified": false,
  "blocked": true,
  "block_reason": "verification_failed",
  "model_call_error": null,
  "surface_report": null,
  "verification": { "...": "a VerificationReport" },
  "attempts": [{"number": 1, "outcome": "verification_failed", "...": "generation-loop's attempt entry"}],
  "license_scan": { "...": "a LicenseScanResult" },
  "secret_scan": { "...": "a SecretScanResult" }
}
```

Every nested value is the dependency's own value, passed through
unchanged: never copied or converted.

A short-circuiting hit (`R-GATE-001`) is a `check_provenance` result
whose `hit` is true, whose `verification_report.overall` is `"pass"`
and whose `license_scan.blocked` is not `true`. Then `provenance_hit` is
`true`, `verification`/`license_scan`/`secret_scan` are that result's
`verification_report`/`license_scan`/`secret_scan`, `blocked` is
`false`, `attempts` is `[]`, and the other fields are `null`. Otherwise
`provenance_hit` is `false` and the scans are the two scanners'
results.

On a non-sealed miss (`R-GATE-004`), `verification` is the loop's last
`verification_report` (`null` when none ran), `surface_report` the
loop's last `surface_report` (`null` when none was made: `D359`) and
`attempts` the loop's `attempts` list. When the loop's `passed` is true, `blocked` is
`false` and `block_reason` and `model_call_error` are `null`, whatever
its `generation_result` holds. Otherwise `blocked` is `true` and
`block_reason` comes from the last attempt's `outcome` (`R-GATE-004`);
`stop_reason` is never consulted.
`model_call_error` is the loop's last `generation_result.model_call_error`
(a `{category, message}` value) when `block_reason` is
`"model_call_error"`, else `null`.

After a passing re-verification (`R-GATE-011`), `reverified` is
`true`, `blocked` is `false`, `attempts` is `[]`, `verification` and
the scans are the re-verification's, and the other fields are `null`
or `false`. On every other path `reverified` is `false`.

For a sealed component (`R-GATE-007`), `verification` is `verify`'s
report and `attempts` is `[]`; `blocked` is `true`, with `block_reason`
`"verification_failed"`, exactly when that report's `overall` is
`"fail"`, and otherwise `false` with `block_reason` `null`;
`model_call_error` and `surface_report` are `null`.

`blocked` concerns generation and verification only.
`license_scan.blocked` and `secret_scan.flagged` are reported as-is;
whether they stop a merge is `provenance-tracker`'s readiness check,
not this component's verdict.

Returned as a dict with exactly these keys.
