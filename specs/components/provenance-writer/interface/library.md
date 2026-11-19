# Library

```
write_provenance(component_id: str, inputs: ProvenanceInputs, repo_root: Path) -> None
write_sealed_provenance(component_id: str, inputs: SealedProvenanceInputs, repo_root: Path) -> None
```

`ProvenanceInputs` (see `interface/data/`) bundles the other components'
already-produced results (`GenerationResult`, `VerificationReport` or
`null`, `LicenseScanResult`, `SecretScanResult`, cache/attempt/gate-version
data) — this component does not call any of those components itself, it
only assembles what it's handed.

`write_sealed_provenance` is the sealed counterpart (`R-PROV-018`,
`R-PROV-019`): it writes a sealed component's ownership and verification
manifest (`interface/data/SealedProvenance.md`). It raises
`InvalidSealedInputError`, defined in this module, for any input that
would not yield a valid manifest. `SealedProvenanceInputs` is a real
dataclass in this module, and a plain dict of the same fields is
accepted too (`R-PROV-014`, `R-PROV-017`).

The manifests are the hidden files `<repo_root>/gen/<slug>/.provenance.json`
and `<repo_root>/verification/<slug>/.provenance.json` (and, for a sealed
component, `<repo_root>/<source_path>/.sealed-provenance.json`). Read one by
its exact path, never by a glob such as `*.provenance.json`, which a hidden
file never matches.

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/json-values.md`, `specs/architecture/provenance-writer-fixtures.md`, `specs/architecture/asset-kinds.md`
