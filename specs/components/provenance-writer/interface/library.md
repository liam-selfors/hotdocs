# Library

```
write_provenance(component_id: str, inputs: ProvenanceInputs, repo_root: Path) -> None
```

`ProvenanceInputs` bundles the other components' already-produced results
(`GenerationResult`, `VerificationReport`, `CrossCheckResult` or `None`,
`LicenseScanResult`, `SecretScanResult`, cache/gate-version data) — this
component does not call any of those components itself, it only assembles
what it's handed.
