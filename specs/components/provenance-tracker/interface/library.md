# Library

```
check_readiness(repo_root: Path, changed_ids: list[str] | None = None) -> VerifyReport
```

The live provenance query (`R-TRACK-009`/`010`, `D88`) — "would a merge
pass right now." Omitting `changed_ids` checks the whole corpus.

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
the record. Called once per `hotdocs generate` attempt, by
`component-gate-runner`, regardless of outcome.

```
last_requirement_failures(component_id: str, repo_root: Path) -> list[str]
```

Reads the most recent `AttemptRecord` for `component_id` with a
non-null `verification` and returns its `requirement_results`' failing
`R-id`s, or `[]` if none exists (R-TRACK-008). A pure convenience
lookup for a human deciding what to pass as `--retry-feedback` on
their next `hotdocs generate` call — never called by any component
itself.
