# Components

One subdirectory per component, flat namespace, no nesting:

```
<component>/
  spec.md          # normative behavior
  interface.md     # public contract
  acceptance.md    # acceptance criteria
  constraints.md   # non-functional requirements
```

See `SPEC_GUIDELINES.md` §3.4 (anatomy) and §4 (sizing / when to split).

- **`spec-linter`** — the first one specced in full depth, deliberately: a
  component whose entire acceptance criteria set is `kind: compiled`, as a
  concrete test of D5's own guidance.

Everything else in the pipeline's own architecture
(`specs/architecture/pipeline-decomposition.md`) is declared but not yet
specced to this depth.
