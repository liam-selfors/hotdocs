# Library

```
check_provenance(component_id: str, spec_bundle_hash: str, gate_versions: dict[str, str], repo_root: Path) -> ProvenanceCheckResult
```

Pure function of the working tree's current state plus
`VAR-TRUST-JUDGE-PROVENANCE` — no network access, no model call.
