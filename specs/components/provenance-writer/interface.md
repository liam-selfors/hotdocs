---
id: comp-provenance-writer-interface
title: Provenance Writer — Interface
status: draft
owners: [pipeline-team]
---

# Provenance Writer — Interface

## CLI

```
hotdocs provenance write <component-id> [--repo-root=<dir>]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Manifest written to both required locations. |
| `1` | A required upstream result (e.g. `verifier-orchestrator`'s report) was missing — this component cannot invent what it didn't receive. |
| `2` | Usage error. |

## Library

```
write_provenance(component_id: str, inputs: ProvenanceInputs, repo_root: Path) -> None
```

`ProvenanceInputs` bundles the other components' already-produced results
(`GenerationResult`, `VerificationReport`, `CrossCheckResult` or `None`,
`LicenseScanResult`, `SecretScanResult`, cache/gate-version data) — this
component does not call any of those components itself, it only assembles
what it's handed.

## Data: provenance manifest

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
