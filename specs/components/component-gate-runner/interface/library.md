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
`.hotdocs/attempts/<component_id>/` (`0` when absent) and, after a
passing re-verification, the committed manifest: every other fact about
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
1a. only on a miss whose `reason` is `"environment differs"`
   (`R-GATE-011`): `make_closures` and `verify` as a sealed component's
   steps 1 and 2 below, then both scans as in 4. If they pass (`R-GATE-011`), read
   `<repo_root>/gen/<slug>/.provenance.json` as JSON (`<slug>` is
   `component_id` without `comp-`), call `write_provenance` as in 5
   with `verification_report`, `license_scan_result` and
   `secret_scan_result` these three results, `attempts` and
   `attempt_history` the manifest's, and `generation_result`
   `{"files": {}, "spec_bundle_hash": key.spec_bundle_hash}` plus the
   manifest's `model_pin` as `model`, its `prompt_version` and
   `retry_feedback`, and each field of its `generation` but
   `generator_version`; nothing below is called. Otherwise go on to 2
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
5. only if the loop's last `generation_result` has non-empty `files`
   and its last `verification_report` is not `None` (`R-GATE-006`):
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

CLI: see `interface/cli.md`.

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/json-values.md`
