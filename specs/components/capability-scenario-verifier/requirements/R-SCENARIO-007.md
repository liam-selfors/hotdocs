# R-SCENARIO-007

**R-SCENARIO-007** — `run_capability_gates` MUST build its own
  `test_author` callable from its `model`, `seed`, and `llm_backend`;
  nothing calls it with one already wired (`D92`). Given a scenario
  bundle (`R-SCENARIO-003`), the callable reuses the committed test when
  it is current, and otherwise calls `test-author`'s
  `author_test(criterion_bundle, model, seed=seed, repo_root=repo_root,
  llm_backend=llm_backend)` and returns its result unchanged. The
  `criterion_bundle` is a dict with:

  - `component_id`: `"capabilities/<P-id>"`, so the test lands at
    `verification/capabilities/<P-id>/generated-test/`;
  - `criterion_id`: the scenario id; `covers`: the scenario's `covers`;
  - `criterion_text`: its Gherkin; `requirement_text`: the text of the
    capability's `specs/product/<name>.md`;
  - `interface`: for each realizing component in id order, a line
    `## <component id>` then the text of every `.md` file under its
    `specs/components/<slug>/interface/`, in sorted path order;
  - `glossary`: the text of `specs/glossary.md`, or `""` if absent;
  - `dependency_interfaces`: `{}` — a capability test uses the real
    assembled system, never fakes;
  - `module_names`: each realizing component's slug with hyphens as
    underscores, in id order (`D198`).

  **Reuse** (`D370`): the committed test is
  `verification/capabilities/<P-id>/generated-test/test_<scenario id
  lowercased, - as _>.py`, current when its first line is exactly
  `# hotdocs-criterion: sha256:<hex>`: `<hex>` the lowercase hex SHA-256
  of the UTF-8 of `json.dumps` of the `criterion_bundle`'s
  `criterion_text`, `requirement_text`, `interface` and `glossary`, plus
  `testing` `""`, with `sort_keys=True`, `ensure_ascii=False`,
  `separators=(",", ":")`. A current test is returned as
  `{"model_call_error": None, "file": {"path": <that path>, "content":
  <its text>}}`, `test-author` neither loaded nor called.
