# Library

The importable module is `provenance_checker`
(`gen/provenance-checker/provenance_checker.py`).

```
check_provenance(component_id: str, spec_bundle_hash: str, gate_versions: dict[str, str], repo_root: Path) -> ProvenanceCheckResult
current_provenance_key(component_id: str, repo_root: Path) -> ProvenanceKey
current_sealed_key(component_id: str, repo_root: Path) -> SealedKey | None
check_sealed_provenance(component_id: str, repo_root: Path) -> SealedCheckResult
```

`check_provenance` is a pure function of the working tree's current
state plus `VAR-TRUST-JUDGE-PROVENANCE` — no network access, no model
call, except what an adapter's `provision` does (`R-PROVCHECK-004`).

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
`license_scanner`, `secret_scanner`, `generator`). Only when `<dir>` is
absent under `repo_root` is the tool root's copy used (`D199`). Each is
loaded from its file afresh on every call, never reused from an earlier
`sys.modules` entry, so a stand-in that records its calls does so
through a side channel the test controls, such as a file outside
`repo_root` whose path is written into the stand-in's source. Beyond
loading these and the asset reads below, it reads nothing under
`repo_root`: every other corpus read happens inside `assemble`, so a
stand-in `assemble` needs no `specs/` tree. It reads, in this order:

1. `spec-bundle-assembler`'s `assemble(component_id, repo_root=...,
   mode="cold")`, taking only its `spec_bundle_hash`
2. `criterion-compiler`'s `GATE_VERSION`
3. `test-author`'s `GATE_VERSION`
4. `verifier-orchestrator`'s `GATE_VERSION`
5. `license-scanner`'s `gate_version(repo_root)`
6. `secret-scanner`'s `gate_version(repo_root)`
7. `generator`'s `GATE_VERSION` and `PROMPT_VERSION`

Any stand-in for these dependencies must provide each name this list
gives. No network access, no model call, no write, `provision` aside
(`R-PROVCHECK-004`).

## Assets (`D343`, `D344`)

`current_provenance_key` and `check_provenance` (the latter only after
`spec_bundle_hash` and `gate_versions` match) read the component's
`<repo_root>/specs/components/<slug>/component.md` frontmatter `assets`
and, per kind, the implicit `python` first and then each declared
kind, the repository's definition
`<repo_root>/specs/architecture/asset-kind-<kind>.md`, if any, and the
adapter `asset-kinds.md`'s Lookup finds: `<repo_root>/gen/kind-<kind>/kind_<kind>.py`,
else the tool root's, the tool root as asset-kinds.md defines it. The adapter is loaded by path afresh on every call; only its
`provision(repo_root)` is called (`R-PROVCHECK-009`).

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

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/asset-kinds.md`
