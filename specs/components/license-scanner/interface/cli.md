# CLI

```
hotdocs license-scan <component-id> [--repo-root=<dir>] [--format=json|text]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Clean (below block threshold). |
| `1` | Flagged (at or above block threshold) — merge blocked. |
| `2` | Usage error. |
