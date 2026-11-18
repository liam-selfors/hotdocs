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

Implements: `specs/architecture/capability-scenario-fixtures.md`

## Dependencies

Each is loaded lazily, at its first use, from `repo_root`, or from the
tool root when the directory shown is absent there (`D199`); never by a
bare `import`; as a flat `<module>.py` or
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

A test builds its fixtures and finds the real compiler as
`specs/architecture/capability-scenario-fixtures.md` says.
