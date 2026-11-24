# CLI

```
hotdocs author-test <component-id> <criterion-id> --model=<model-id> [--seed=<n>] [--repo-root=<dir>] [--format=json|text]
```

- `<criterion-id>` — the acceptance criterion's own id (e.g. `AC-FOO-003`).
- `--model` — required, same discipline as `generator`'s `--model`: never
  an implicit default.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Test code produced by a model call and written. |
| `1` | Model-call error (R-AUTHOR-007). |
| `2` | Usage error. |
