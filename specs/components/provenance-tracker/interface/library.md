# Library

```
check_readiness(
    repo_root: Path, changed_ids: list[str] | None = None,
    model: str | None = None, seed: int = 0, llm_backend=None,
) -> VerifyReport
```

The live provenance query (`R-TRACK-009`/`010`, `D88`/`D93`) — "would a
merge pass right now." Omitting `changed_ids` checks the whole corpus.
Every component is checked against `provenance-checker` only: first its
`current_sealed_key`, whose `None` means a generated component, checked
with `current_provenance_key` and `check_provenance`, and whose key means
a sealed one, checked with `check_sealed_provenance` (`D170`). Any stand-in
for `provenance-checker` must provide all four names, `current_sealed_key`
returning `None` for a component that is not sealed. It is a pure read, never a call to `component-gate-runner` (`D93`). Every
intersecting capability is first checked with
`capability-scenario-verifier`'s `check_capability_provenance`; only a
miss is run with `run_capability_gates`, passing `model`/`seed`/
`llm_backend` straight through unchanged (`R-TRACK-010`). `model` is
optional here, unlike `component-gate-runner`'s `run_component_gates`:
it is only consulted for such a miss, and a miss with `model` still
`None` raises `ValueError`, never silently skipped.

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
