# Library

```
check_provenance(component_id: str, spec_bundle_hash: str, gate_versions: dict[str, str], repo_root: Path) -> ProvenanceCheckResult
current_provenance_key(component_id: str, repo_root: Path) -> ProvenanceKey
current_sealed_key(component_id: str, repo_root: Path) -> SealedKey | None
check_sealed_provenance(component_id: str, repo_root: Path) -> SealedCheckResult
```

`check_provenance` is a pure function of the working tree's current
state plus `VAR-TRUST-JUDGE-PROVENANCE` — no network access, no model
call.

`current_provenance_key` is the one definition of the values a caller
passes to `check_provenance`, and that `component-gate-runner` passes
to `provenance-writer` (`R-PROVCHECK-005`, `D163`). It loads each
dependency from `<repo_root>/gen/<slug>/`, or for the sealed
`criterion-compiler` from its `source_path`, `pipeline/criterion-compiler/`,
and reads, in this order:

1. `spec-bundle-assembler`'s `assemble(component_id, repo_root=...,
   mode="cold")`, taking only its `spec_bundle_hash`
2. `criterion-compiler`'s `GATE_VERSION`
3. `test-author`'s `GATE_VERSION`
4. `verifier-orchestrator`'s `GATE_VERSION`
5. `license-scanner`'s `gate_version(repo_root)`
6. `secret-scanner`'s `gate_version(repo_root)`

Any stand-in for these dependencies must provide each name this list
gives. No network access, no model call, no write.

## Sealed components (`D170`)

`current_sealed_key` is also the one test of whether a component is
sealed: it returns `None` for a component that is not (`R-PROVCHECK-007`).
Callers (`component-gate-runner`, `provenance-tracker`) route on it
rather than reading `component.md` themselves. It reads
`<repo_root>/specs/components/<slug>/component.md` and, for
`verifier_version`, `verifier-orchestrator`'s `GATE_VERSION` from
`<repo_root>/gen/verifier-orchestrator/`. `check_sealed_provenance`
reads the sealed manifest (`provenance-writer`'s
`interface/data/SealedProvenance.md`) and compares it to the current
key (`R-PROVCHECK-008`). Both are read-only and make no network or
model call. Any stand-in for `verifier-orchestrator` provides
`GATE_VERSION`.
