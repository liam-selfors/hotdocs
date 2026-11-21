---
id: arch-capability-scenario-fixtures
title: Capability Scenario Fixtures
status: draft
owners: [pipeline-team]
depends_on: []
---

# Capability Scenario Fixtures

## Purpose

The shapes a `capability-scenario-verifier` test builds its fixtures
from, and where it finds the real criterion compiler (`D336`).

## Rules

A test builds a temporary `repo_root` and supplies `test-author` and
`llm-endpoint` as small fake modules at the paths the interface's
Dependencies section shows. A fake embeds no secret-shaped string.

**The real compiler.** A test that needs it copies
`<live>/pipeline/criterion-compiler/` to
`<repo_root>/pipeline/criterion-compiler/`, where `<live>` is

    (Path(capability_scenario_verifier.__file__).resolve().parents[1]
     / "llm-endpoint").resolve().parents[1]

that is, the tree holding the `gen/llm-endpoint/` directory beside the
module's own. A mutation run copies only the module's own `gen/<slug>/`
and links every other `gen/` directory to the tree the criterion run
used (`specs/architecture/mutation-runs.md`), so `<live>` is that tree
in both runs, while the module's own parents, the current directory and
the test file's location are not. A test never skips because the
compiler is missing. A test that compiles nothing supplies no compiler.

**The shapes.** Every fixture uses exactly these, because the code under
test reads them and nothing else:

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
