# Library

```
write_provenance(component_id: str, inputs: ProvenanceInputs, repo_root: Path) -> None
```

`ProvenanceInputs` (see `interface/data/`) bundles the other components'
already-produced results (`GenerationResult`, `VerificationReport` or
`null`, `LicenseScanResult`, `SecretScanResult`, cache/attempt/gate-version
data) — this component does not call any of those components itself, it
only assembles what it's handed.
