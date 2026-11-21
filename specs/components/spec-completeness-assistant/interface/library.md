# Library

```
assist(
    changed_ids: list[str], repo_root: Path, model: str | None = None,
    *, llm_backend=None,
) -> CompletenessReport
main(argv: list[str]) -> int
```

One flat module file, `spec_completeness_assistant.py`, never a package
and importing no sibling file of its own. `model` omitted runs in
degraded mode (R-ASSIST-007); given, it is dispatched via `llm-endpoint`
— this component holds no credential. `llm_backend` is passed unchanged
to `spec-reviewer` and `llm-endpoint`. `assist` reports every outcome,
a halt included, only through its return value, and creates, modifies or
deletes no file under `repo_root`.

`changed_ids` holds spec ids. The **changed components** are each
`comp-<slug>` named, plus the component whose directory holds a
requirement or criterion file named `<id>.md` for each other id. The
**changed requirements** are each `R-` id named, plus every requirement
of each `comp-` id named. A requirement's **covering criteria** are the
files under its own component's `acceptance/` whose `Covers:` line names
it. All are read from `<repo_root>/specs/components/`; an id that names
nothing, or a missing `specs/components/`, contributes nothing and
raises nothing. A lint finding is **inside** a changed component when
its `file`, relative to `repo_root` with `/` separators, starts with
`specs/components/<slug>/` for that component's slug.

Each dependency is one flat module file, loaded per `R-ASSIST-011`,
called in this order, stopping after step 2 on a halt (`R-ASSIST-001`):

1. with a `model` only: `spec-reviewer`'s `glossary_judge(model, llm_backend)`
2. `spec-linter`'s `lint(None, repo_root, judge=<that judge, or None>)`
3. `impact-analyzer`'s `compute_blast_radius(changed_ids, repo_root)`,
   `changed_ids` exactly as received
4. `spec-reviewer`'s `check([component_id], repo_root)`, no other
   argument, once per blast-radius component, in that order
5. with a `model` only: `llm-endpoint`'s `complete(prompt, model,
   backend=llm_backend)` for completeness, always, then a second time for
   redundancy only when `R-ASSIST-005` finds a candidate pair. No other
   `complete` call is made.

A completeness reply's `text` is `{"completeness_score": <0.0–1.0>,
"completeness_rationale": "<text>"}`, a redundancy reply's
`{"redundancy_flags": [<entry>, ...]}`, parsed per `R-ASSIST-010`. A
reply that does not parse, or a `model_call_error`, leaves that call's
fields `null`/`[]`, never raises and does not affect the other call.

## Test fixtures

Each dependency is replaced by a stand-in module written to
`<repo_root>/gen/<slug>/<module>.py`: `spec_linter.py`,
`impact_analyzer.py`, `spec_reviewer.py`, `llm_endpoint.py`, each with
its real signature's full parameter list:

- `lint(paths, repo_root, strict=False, judge=None)` returning an object
  or dict whose `findings` lists findings, each an object or dict with
  `rule_id`, `severity`, `file`, `line`, `message`;
- `compute_blast_radius(changed_ids, repo_root)` returning an object or
  dict whose `impacted` lists entries, each an object or dict with a
  `component_id`;
- `check(targets, repo_root, model=None, *, llm_backend=None,
  write_proposals=False)` returning an object with a `to_dict()`;
- `glossary_judge(model, llm_backend=None)` returning any callable,
  which `assist` only passes to `lint`;
- `complete(prompt, model, backend=None, **params)` returning a dict
  with `text` and `model_call_error`.

`assist` reads every such field as a key or an attribute, whichever is
given; a missing `precondition_error` counts as `null`. A stand-in may
answer `complete` by call index.

Implements: `specs/architecture/cli-conventions.md`
