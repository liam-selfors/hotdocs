# Library

The importable module is `provenance_checker`
(`gen/provenance-checker/provenance_checker.py`).

```
check_provenance(component_id: str, spec_bundle_hash: str, gate_versions: dict[str, str], repo_root: Path, spec_bundle_parts: dict | None = None) -> ProvenanceCheckResult
current_provenance_key(component_id: str, repo_root: Path) -> ProvenanceKey
current_sealed_key(component_id: str, repo_root: Path) -> SealedKey | None
check_sealed_provenance(component_id: str, repo_root: Path) -> SealedCheckResult
```

`current_provenance_key` is the one definition of the values a caller
passes to `check_provenance`, and that `component-gate-runner` passes
to `provenance-writer` (`R-PROVCHECK-005`, `D163`). It loads each
dependency from a directory `<dir>`: the fixed path
`<repo_root>/pipeline/criterion-compiler/` for the sealed
`criterion-compiler`, and `<repo_root>/gen/<slug>/` for every other;
it reads no `component.md` to find them. The module is
`<dir>/<module>.py`, else `<dir>/<module>/__init__.py`, where `<module>`
is the slug with hyphens replaced by underscores (`spec_bundle_assembler`,
`criterion_compiler`, `test_author`, `verifier_orchestrator`,
`license_scanner`, `secret_scanner`, `generator`, `run_environment`). Only when `<dir>` is
absent under `repo_root` is the tool root's copy used (`D199`). Each is
loaded from its file afresh on every call, never reused from an earlier
`sys.modules` entry. Beyond
loading these and the asset reads below, it reads nothing under
`repo_root`: every other corpus read happens inside `assemble`. It reads, in this order:

1. `spec-bundle-assembler`'s `assemble(component_id, repo_root=...,
   mode="cold")`, taking only its `spec_bundle_hash` and `spec_bundle_parts`
2. `criterion-compiler`'s `GATE_VERSION`
3. `test-author`'s `GATE_VERSION`
4. `verifier-orchestrator`'s `GATE_VERSION`
5. `license-scanner`'s `gate_version(repo_root)`
6. `secret-scanner`'s `gate_version(repo_root)`
7. `generator`'s `GATE_VERSION` and `PROMPT_VERSION`

## Assets and drivers (`D343`, `D373`)

`current_provenance_key` and `check_provenance` (the latter only after
`spec_bundle_hash` and `gate_versions` match) take a component's assets
and drivers values from `run-environment`'s `prepare`, loaded from
`<repo_root>/gen/run-environment/`, else the tool root's
(`R-PROVCHECK-009`). A miss in `versions` or `lockfile_sha256` alone is
`environment differs` (`R-PROVCHECK-010`, `D345`).

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
model call.

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/asset-kinds.md`
