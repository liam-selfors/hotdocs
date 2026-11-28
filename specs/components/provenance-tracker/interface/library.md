# Library

One module file, `provenance_tracker.py`, never a package: `hotdocs-cli`
loads it by that path.

```
check_readiness(
    repo_root: Path, changed_ids: list[str] | None = None,
    model: str | None = None, seed: int = 0, llm_backend=None,
) -> VerifyReport
```

"Would a merge pass right now" (`R-TRACK-009`/`010`/`016`); omitting
`changed_ids` checks the whole corpus. Any stand-in for
`provenance-checker` must provide `current_sealed_key` (returning `None`
for a component that is not sealed), `current_provenance_key`,
`check_provenance` and `check_sealed_provenance` (`D170`). `model` is
consulted only for a capability miss (`R-TRACK-010`).

```
write_attempt_record(
    component_id: str,
    generation_result: GenerationResult,
    verification_report: VerificationReport | None,
    spec_bundle_hash: str,
    repo_root: Path,
) -> AttemptRecord
```

Writes to `.hotdocs/attempts/<component_id>/` (R-TRACK-007) and returns
the record.

```
last_requirement_failures(component_id: str, repo_root: Path) -> list[str]
```

Reads the most recent `AttemptRecord` for `component_id` with a
non-null `verification` and returns its `requirement_results`' failing
`R-id`s, or `[]` if none exists (R-TRACK-008).

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/json-values.md`, `specs/architecture/repository-secret-scan.md`
