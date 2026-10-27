# Library

```
generate(
    bundle: SpecBundle, model: str, retry_feedback: list[str] | None = None,
    *, repo_root: Path = None, llm_backend=None,
) -> GenerationResult
```

Not a pure function — this is the one component in the corpus whose job
requires an external call. Side effects: in `cold` mode, writes
`gen/<component>/` and writes through `cache-manager`; in `hint` mode,
reads through `cache-manager` but writes to neither destination
(`R-GEN-016`).

`repo_root` and `llm_backend` (added to fill two real, pre-existing
gaps) — `repo_root` locates `specs/components/<name>/component.md`'s
`sealed`/`source_path` frontmatter and `gen/<component>/.overrides.json`
for `R-GEN-009`'s precondition check, and the write target for
`gen/<component>/` itself; `bundle` alone never carried this (its
`spec` field excludes frontmatter by construction, `R-ASSEMBLE-001`),
so there was never a way to resolve either from the bundle alone.
`llm_backend`, passed straight through to `llm-endpoint`'s own
`backend` parameter, is how `AC-GEN-001`–`013`'s "injected mock model"
is actually wired in — every one of this component's own
`generated-test` criteria already required one.
