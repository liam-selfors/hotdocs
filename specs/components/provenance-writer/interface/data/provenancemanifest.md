# provenance manifest

The schema is `SPEC_GUIDELINES.md` §8 itself, reproduced here only for
convenience, not as a second definition:

```json
{
  "spec_bundle_hash": "sha256:...",
  "model_pin": "claude-sonnet-5",
  "prompt_version": "v1",
  "sample_index": 0,
  "pipeline_version": "v1",
  "gate_versions": { "compiler": "1.0.0", "license_scanner": "k-gram@1.0.0" },
  "cache_hit": false,
  "generated_at": "2026-01-01T00:00:00Z",
  "verification_run_id": "run-123",
  "verification_report": { "...": "a VerificationReport" },
  "cross_model_check": "not-run",
  "license_scan": { "...": "a LicenseScanResult" },
  "secret_scan": { "...": "a SecretScanResult" }
}
```
