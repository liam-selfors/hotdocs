# CLI

```
hotdocs provenance write <component-id> [--repo-root=<dir>]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Manifest written to both required locations. |
| `1` | A required upstream result (e.g. `verifier-orchestrator`'s report) was missing — this component cannot invent what it didn't receive. |
| `2` | Usage error. |
