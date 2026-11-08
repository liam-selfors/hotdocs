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
`generator` and `llm-endpoint` unchanged, the same injection point
every other model-calling component in this corpus exposes (`D156`).

Each dependency is loaded from `<repo_root>/gen/<slug>/`, or from the
tool root's when absent (`D199`), and called in
this order, stopping early per `R-ASSIST-001`:

1. `spec-linter`'s `lint(paths, repo_root)`
2. `impact-analyzer`'s `compute_blast_radius(changed_ids, repo_root)`
3. for each component in the blast radius: `spec-bundle-assembler`'s
   `assemble(component_id, repo_root=..., mode="hint")`, then, with a
   `model` only, `generator`'s `generate(bundle, model, None,
   repo_root=..., llm_backend=...)`
4. with a `model` only: `llm-endpoint`'s `complete(prompt, model,
   backend=llm_backend)`, called exactly twice — completeness first,
   then redundancy — each response parsed per `R-ASSIST-010`

Any stand-in for these dependencies must provide each function this
list names, with the full parameter list of its real signature (a
`lint` stand-in takes `(paths, repo_root, strict=False, judge=None)`).
