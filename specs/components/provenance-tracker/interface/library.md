# Library

```
check_readiness(
    repo_root: Path, changed_ids: list[str] | None = None,
    model: str | None = None, seed: int = 0, llm_backend=None,
) -> VerifyReport
```

The live provenance query (`R-TRACK-009`/`010`, `D88`/`D93`) — "would a
merge pass right now." Omitting `changed_ids` checks the whole corpus.
Every component is checked against `provenance-checker` only, using
its `current_provenance_key` — a pure read, never a call to `component-gate-runner` (`D93`). Every
intersecting capability is checked-then-run against
`capability-scenario-verifier`'s `run_capability_gates`, passing
`model`/`seed`/`llm_backend` straight through unchanged (`D89`/`D92`).
`model` is optional here, unlike `component-gate-runner`'s own
`run_component_gates` — it is only consulted if some capability in
scope is a provenance miss and needs a fresh scenario run; a miss
encountered with `model` still `None` is reported as a usage error, not
silently skipped.

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
