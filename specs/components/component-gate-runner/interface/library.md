# Library

One module file, `component_gate_runner.py`, never a package;
`run_component_gates` and `main` are its top-level names.

```
run_component_gates(
    component_id: str, repo_root: Path, model: str, seed: int = 0,
    llm_backend=None, retry_feedback: list[str] | None = None, *,
    max_attempts: int = 3, mode: str = "single", allow_unisolated_exec: bool = False,
) -> ComponentPipelineResult
```

`model`/`seed`/`llm_backend` are this component's own parameters
(`D86`). `retry_feedback`, `max_attempts`, `mode` and
`allow_unisolated_exec` go to `generation-loop`'s `run_attempts`
unchanged, and `repo_root` goes to every dependency exactly as
received, never resolved or converted. `run_component_gates` validates
nothing itself and reads no file except to count
`.hotdocs/attempts/<component_id>/` (`0` when absent): every fact about
the component comes from its dependencies.

Each dependency `<slug>` is loaded from
`<repo_root>/gen/<slug>/<module>.py`, `<module>` being `<slug>` with
each `-` replaced by `_`, else from the tool root's copy (`D199`); each
`run_component_gates` call loads afresh, and only when a module's first
call is about to be made. Every call passes its arguments in the form
shown, positional or keyword. The first call, for every component, is
`provenance-checker`'s `current_sealed_key(component_id, repo_root)`: a
non-`None` result means the component is sealed and only the sealed
calls below are made (`D170`). On a non-sealed component, the calls
are, in this order:

1. `provenance-checker`'s `current_provenance_key(component_id,
   repo_root)`, then `check_provenance(component_id,
   key.spec_bundle_hash, key.gate_versions, repo_root)` — on a
   short-circuiting hit (`interface/data/ComponentPipelineResult.md`),
   nothing below is called
2. `spec-bundle-assembler`'s `assemble(component_id,
   repo_root=repo_root, mode="cold")`
3. `generation-loop`'s `run_attempts(component_id, bundle, repo_root,
   model, mode=mode, max_attempts=max_attempts,
   retry_feedback=retry_feedback, seed=seed, llm_backend=llm_backend,
   allow_unisolated_exec=allow_unisolated_exec, on_attempt=<callback>)`,
   which builds its own closures (`make_closures` is never called on
   this path); the callback passes its `generation_result` and
   `verification_report` arguments, unchanged, to `provenance-tracker`'s
   `write_attempt_record(component_id, generation_result,
   verification_report, key.spec_bundle_hash, repo_root)`
4. `license-scanner`'s `scan(component_id, repo_root)`, then
   `secret-scanner`'s `scan(repo_root)`
5. only if the loop's last `generation_result` has non-empty `files`:
   `provenance-writer`'s `write_provenance(component_id, inputs,
   repo_root)`, `inputs` the plain dict `{component_id,
   generation_result, verification_report, license_scan_result,
   secret_scan_result, provenance_hit: false, attempts,
   attempt_history, gate_versions: key.gate_versions}`: the loop's last
   results, the two scans', `attempts` the file count above taken after
   the loop, and `attempt_history` the loop's `attempts`

A sealed component (`R-GATE-007`) then makes exactly these calls, in
this order, and never `run_attempts`:

1. `generation-loop`'s `test_author, judge = make_closures(model, seed,
   repo_root, llm_backend)`
2. `verifier-orchestrator`'s `verify(component_id, repo_root,
   judge=judge, test_author=test_author)`
3. `license-scanner`'s `scan(component_id, repo_root)`, then
   `secret-scanner`'s `scan(repo_root)`
4. `provenance-writer`'s `write_sealed_provenance(component_id,
   inputs, repo_root)`, `inputs` the plain dict `{component_id, owners,
   source_path, source_hash, verifier_version, verification_report}`:
   the `SealedKey`'s four values and `verify`'s report

No dependency name beyond these lists is used: `ProvenanceInputs` is a
dict, never a class from `provenance-writer`. Results from every
dependency are read with dual dict-or-attribute access.

Test fixtures: each dependency is a stand-in at
`<repo_root>/gen/<slug>/<module>.py` (`provenance-checker/provenance_checker.py`,
`spec-bundle-assembler/spec_bundle_assembler.py`,
`generation-loop/generation_loop.py`,
`provenance-tracker/provenance_tracker.py`,
`verifier-orchestrator/verifier_orchestrator.py`,
`license-scanner/license_scanner.py`, `secret-scanner/secret_scanner.py`,
`provenance-writer/provenance_writer.py`) providing the names above and
recording each call, with its arguments, to a file. A stand-in may
return plain dicts; a `run_attempts` stand-in returns a dict with
`AttemptLoopResult`'s keys and calls `on_attempt` only when its test
says so. A CLI test's `repo_root` also holds
`specs/components/<slug>/component.md` (`interface/cli.md`);
`run_component_gates` itself needs none.

CLI: see `interface/cli.md`.

Implements: `specs/architecture/cli-conventions.md`
