# Library

```
run_component_gates(
    component_id: str, repo_root: Path, model: str, seed: int = 0,
    llm_backend=None, retry_feedback: list[str] | None = None,
) -> ComponentPipelineResult
```

`model`/`seed`/`llm_backend` are this component's own parameters
(`D86`): it builds its own `test_author` and `judge` closures from
them (`R-GATE-002`, `R-GATE-010`). `retry_feedback` (`R-GATE-003`,
`D3`) is passed through to `generator` unchanged, never derived here.

Each dependency is loaded from `<repo_root>/gen/<slug>/`, or from the tool root's when absent (`D199`). The first
call, for every component, is `provenance-checker`'s
`current_sealed_key(component_id, repo_root)`: a non-`None` result means
the component is sealed and only the sealed calls below are made
(`D170`); `None` means every call in the next list, whose own first call
is `current_provenance_key`. On a non-sealed component, the calls are,
in this order:

1. `provenance-checker`'s `current_provenance_key(component_id,
   repo_root)`, then `check_provenance(component_id,
   key.spec_bundle_hash, key.gate_versions, repo_root)` — on a
   short-circuiting hit (`R-GATE-001`), nothing below is called
2. `spec-bundle-assembler`'s `assemble(component_id,
   repo_root=repo_root, mode="cold")`
3. `generator`'s `generate(bundle, model, retry_feedback,
   repo_root=repo_root, llm_backend=llm_backend)`
4. only if that result's `files` is non-empty: `verifier-orchestrator`'s
   `verify(component_id, repo_root, judge=<judge closure>,
   test_author=<test_author closure>)`
5. `license-scanner`'s `scan(component_id, repo_root)`, then
   `secret-scanner`'s `scan(repo_root)`
6. `provenance-tracker`'s `write_attempt_record(component_id,
   generation_result, verification_report_or_None,
   key.spec_bundle_hash, repo_root)`
7. only if step 3 produced files: `provenance-writer`'s
   `write_provenance(component_id, inputs, repo_root)`, with
   `ProvenanceInputs` as a plain dict `{component_id, generation_result,
   verification_report, license_scan_result, secret_scan_result,
   provenance_hit: false, attempts, gate_versions: key.gate_versions}`,
   where `attempts` is the number of files in
   `.hotdocs/attempts/<slug>/` after step 6

The `test_author` closure calls `test-author`'s
`author_test(criterion_bundle, model, seed=seed, repo_root=repo_root,
llm_backend=llm_backend)`. The `judge` closure calls `llm-endpoint`'s
`complete(prompt, model, backend=llm_backend)` (`R-GATE-010`).

A sealed component (`R-GATE-007`) makes exactly these calls, in this
order, passing both closures to `verify`:

1. `verifier-orchestrator`'s `verify(component_id, repo_root,
   judge=<judge closure>, test_author=<test_author closure>)`
2. `license-scanner`'s `scan(component_id, repo_root)`, then
   `secret-scanner`'s `scan(repo_root)`
3. `provenance-writer`'s `write_sealed_provenance(component_id,
   inputs, repo_root)`, with `inputs` a plain dict `{component_id,
   owners, source_path, source_hash, verifier_version,
   verification_report}`: `owners`, `source_path`, `source_hash`, and
   `verifier_version` are the `SealedKey`'s, `component_id` is the
   argument, and `verification_report` is the report from call 1

Each dependency module is loaded only when its first call is about to
be made, never earlier — a path that never reaches a call never loads
that module (the same rule `provenance-tracker`'s `R-TRACK-009` states).
No dependency name beyond this list is used: in particular,
`ProvenanceInputs` is a dict, never a class from `provenance-writer`.
Any stand-in for these dependencies must provide each name this list
gives. Results from every dependency are read with dual
dict-or-attribute access.

CLI: see `interface/cli.md`.

Implements: `specs/architecture/json-values.md`
