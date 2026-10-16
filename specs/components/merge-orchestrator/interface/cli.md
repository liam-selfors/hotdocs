# CLI

```
hotdocs merge --changed=<spec-id>... [--repo-root=<dir>] [--format=json|text]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Merge succeeded — all gates passed, atomic commit made. |
| `1` | Merge blocked (R-MERGE-011). |
| `2` | Usage error. |
