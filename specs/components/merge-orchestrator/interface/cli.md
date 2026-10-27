# CLI

```
hotdocs merge --changed=<spec-id>... [--repo-root=<dir>] [--format=json|text]
             [--retry-feedback=<component-id>=<R-id>[,<R-id>...]]...
```

- `--retry-feedback` — repeatable, one per component. Explicitly tells
  `generator`'s one call for that component to include the named
  `R-id`s as `retry_feedback` (`R-MERGE-022`, `D3`). Never inferred
  automatically from a prior attempt — see `hotdocs track feedback` for
  the convenience lookup that tells a developer what to pass here, which
  they still have to choose to pass.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Merge succeeded — all gates passed, atomic commit made. |
| `1` | Merge blocked (R-MERGE-011). |
| `2` | Usage error. |
