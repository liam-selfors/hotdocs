# `component_context` (view)

```
component_id  TEXT  -- comp-id
purpose       TEXT  -- the component's Purpose section text, verbatim
```

One row per component (`R-GQE-004`). Deliberately narrower than
`component_docs` — the one slice of a component's own file that's
dependent-safe to hand to another component (`spec-bundle-assembler`'s
`dependency_context`, `D35`), since `D34` made `Purpose` carry no
decision citations or historical rationale by construction
(`R-LINT-024`).
