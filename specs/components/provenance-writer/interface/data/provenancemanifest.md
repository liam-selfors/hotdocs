# provenance manifest

The manifest's definition: its top-level keys are exactly these
(`D377`).

```json
{
  "spec_bundle_hash": "sha256:...",
  "model_pin": "claude-sonnet-5",
  "prompt_version": "v1",
  "retry_feedback": null,
  "generation": {"mode": "single", "generator_version": "generator@3.0.0+v11",
                 "transcript_sha256": null, "turns": 1, "tool_calls": 0, "isolation": null},
  "attempts": 2,
  "attempt_history": [{"number": 1, "outcome": "verification_failed", "retry_feedback": [],
                       "error_category": null, "failed_requirements": ["R-FOO-002"],
                       "transcript_sha256": null}],
  "pipeline_version": "v1",
  "gate_versions": { "compiler": "1.0.0", "license_scanner": "k-gram@1.0.0" },
  "provenance_hit": false,
  "generated_at": "2026-01-01T00:00:00Z",
  "verification_run_id": "run-123",
  "verification_report": { "...": "a VerificationReport" },
  "license_scan": { "...": "a LicenseScanResult" },
  "secret_scan": { "...": "a SecretScanResult" },
  "assets": [{"kind": "javascript", "path": "static/app.js", "definition_sha256": "sha256:...",
              "adapter_sha256": "sha256:...", "versions": {"node": "24.1.0"},
              "lockfile_sha256": null}]
}
```

`assets` is the `verification_report`'s, verbatim (`R-PROV-022`).
