# Library

```
run_capability_scenarios(blast_radius: list[str], repo_root: Path, judge=None, test_author=None) -> CapabilityScenarioReport
check_capability_provenance(capability_id: str, repo_root: Path) -> CapabilityProvenanceCheckResult
run_capability_gates(capability_id: str, repo_root: Path, model: str | None = None, seed: int = 0, llm_backend=None) -> CapabilityProvenanceCheckResult
GATE_VERSION: str  # "capability_scenario_verifier@2.0.0" (R-SCENARIO-006)
class UnknownCapabilityError(ValueError)
class ModelRequiredError(ValueError)
```

`run_capability_scenarios` takes injected `judge`/`test_author`
callables of the shape the glossary defines under
"Injected `judge`/`test_author` callable shape" (`D65`), read
duck-typed on the way out. `run_capability_gates`
takes `model`, `seed`, and `llm_backend` instead and builds those
callables itself (`R-SCENARIO-007`, `R-SCENARIO-008`); this is the one
function `provenance-tracker`'s `hotdocs verify` calls, as
`run_capability_gates(capability_id, repo_root, model, seed,
llm_backend)`, passing its own three values through unchanged, after
`check_capability_provenance(capability_id, repo_root)` (`R-TRACK-010`).
A developer never invokes this component directly: it has no CLI
(`D92`, `D174`).

## Dependencies

Each is loaded lazily, at its first use, from `repo_root` — never by a
bare `import`, never relative to this file — as a flat `<module>.py` or
a `<module>/__init__.py` package under the directory shown, and its
results are read with dual dict-or-attribute access. No name beyond
these is used.

- `criterion-compiler`, a sealed component, from
  `<repo_root>/pipeline/criterion-compiler/`: `criterion_compiler.
  ParsedCriterion(criterion_id=, covers=, kind=, gherkin=, file=)`, and
  `compile_criterion(parsed, surface=None)`, returning `{"status":
  "compiled", "source": <pytest source>}` or `{"status": "error",
  "message": <text>}`.
- `test-author`, from `<repo_root>/gen/test-author/`: `test_author.
  author_test(bundle, model, seed=, repo_root=, llm_backend=)`, whose
  result has `model_call_error` and `file` (`path`, `content`).
- `llm-endpoint`, from `<repo_root>/gen/llm-endpoint/`: `llm_endpoint.
  complete(prompt, model, backend=)`, whose response has `text` and
  `model_call_error` (with `message`).

## Test fixtures

A test builds a temporary `repo_root` and supplies `test-author` and
`llm-endpoint` as small fake modules at the paths above, and copies the
real compiler from the live repository's `pipeline/criterion-compiler/`
to the same relative path. A fake embeds no secret-shaped string. Every
fixture uses exactly these shapes, because the code under test reads
them and nothing else:

- a component: `specs/components/<slug>/component.md` with frontmatter
  `id: comp-<slug>`, `realizes: [P-X]`, `sealed: false`, plus its code
  under `gen/<slug>/` (a sealed one instead has `sealed: true`,
  `source_path: pipeline/<slug>/`, and its code there);
- a capability: `specs/product/<name>.md` — never `specs/capabilities/`
  — with frontmatter `id: P-X`, then one `### CS-X-001` section per
  scenario holding `Covers: P-X`, `Kind: <kind>`, and a fenced
  `gherkin` block of plain `Given`/`When`/`Then` lines, no `Scenario:`;
- a fake `author_test` result: `{"model_call_error": None, "file":
  {"path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
  "content": "def test_x():\n    assert True\n"}}` — the `path` is always
  repo-relative under `verification/`;
- a fake `author_test` is called as `author_test(bundle, model, seed=,
  repo_root=, llm_backend=)` with `R-SCENARIO-007`'s dict, so it reads
  `bundle["criterion_id"]` (the scenario id) and `bundle["criterion_text"]`
  (its Gherkin), never `scenario_id` or `gherkin`; only a callable
  passed to `run_capability_scenarios` receives the `R-SCENARIO-003`
  bundle with `scenario_id`. A fake `complete(prompt, model, backend=)`
  returns `{"text": ..., "model_call_error": None}`;
- a report: `{"P-X": {"overall": ..., "scenarios": [{"id": ..., "kind":
  ..., "result": ...}]}}`.
