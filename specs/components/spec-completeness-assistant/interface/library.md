# Library

```
assist(
    changed_ids: list[str], repo_root: Path, model: str | None = None,
    *, llm_backend=None,
) -> CompletenessReport
```

`model` omitted (the default) runs in degraded mode, per R-ASSIST-007.
When present, dispatched via `llm-endpoint` (D18) — this component holds
no credential of its own. `llm_backend` is passed straight through to
`spec-reviewer` and `llm-endpoint` unchanged.

`changed_ids` holds spec ids. The **changed components** are each
`comp-<slug>` named, plus the component whose directory holds a
requirement or criterion file named `<id>.md` for each other id. The
**changed requirements** are each `R-` id named, plus every requirement
of each `comp-` id named. A requirement's **covering criteria** are the
files under its own component's `acceptance/` whose `Covers:` line names
it. All are read from `<repo_root>/specs/components/`; an id that names
no directory or file contributes nothing.

Each dependency is one flat module file, `<repo_root>/gen/<slug>/<module>.py`,
or the tool root's when that directory is absent (`R-ASSIST-011`), called in
this order, stopping early per `R-ASSIST-001`:

1. with a `model` only: `spec-reviewer`'s `glossary_judge(model, llm_backend)`
2. `spec-linter`'s `lint(None, repo_root, judge=<that judge, or None>)`
3. `impact-analyzer`'s `compute_blast_radius(changed_ids, repo_root)`
4. `spec-reviewer`'s `check([component_id], repo_root)`, no model, once
   per component in the blast radius, in blast-radius order
5. with a `model` only: `llm-endpoint`'s `complete(prompt, model,
   backend=llm_backend)` for completeness, then once more for redundancy
   only when `R-ASSIST-005` finds a candidate pair

## Test fixtures

Each dependency is replaced by a stand-in module written to
`<repo_root>/gen/<slug>/<module>.py`: `spec_linter.py`,
`impact_analyzer.py`, `spec_reviewer.py`, `llm_endpoint.py`. A stand-in
must provide each function this list names, with the full parameter list
of its real signature: `lint(paths, repo_root, strict=False, judge=None)`;
`compute_blast_radius(changed_ids, repo_root)` returning an object or dict
whose `impacted` lists entries each with a `component_id`; `check(targets, repo_root, model=None, *,
llm_backend=None, write_proposals=False)` returning an object with a
`to_dict()`; `glossary_judge(model, llm_backend=None)`; and
`complete(prompt, model, backend=None, **params)` returning a dict with
`text` and `model_call_error`.
