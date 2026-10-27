# Library

```
check_readiness(
    repo_root: Path, model: str, seed: int = 0, llm_backend=None,
    changed_ids: list[str] | None = None,
    retry_feedback: list[str] | None = None,
) -> VerifyReport
```

`D92`. Brings every component and capability in scope to current,
passing provenance, calling `component-gate-runner`'s
`run_component_gates` and `capability-scenario-verifier`'s
`run_capability_gates` — each already check-then-do, so this never
re-derives hit/miss logic itself. `model`/`seed`/`llm_backend` are
passed straight through to both, unchanged — this component never
constructs or wires anything model-related itself, same as before;
`model` is required, no implicit default, same posture
`generator`/`component-gate-runner` already held individually.
Omitting `changed_ids` checks the whole corpus. `retry_feedback` is
valid only when `changed_ids` names exactly one component — a usage
error otherwise.

```
last_requirement_failures(component_id: str, repo_root: Path) -> list[str]
```

Reads the most recent `AttemptRecord` under `.hotdocs/attempts/`
(written directly by `component-gate-runner`, `R-GATE-008`) for
`component_id` with a non-null `verification` and returns its
`requirement_results`' failing `R-id`s, or `[]` if none exists
(R-TRACK-008). A pure convenience lookup for a human deciding what to
pass as `--retry-feedback` on their next `hotdocs build` call.
