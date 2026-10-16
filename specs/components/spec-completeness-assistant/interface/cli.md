# CLI

```
hotdocs assist --changed=<spec-id>... [--repo-root=<dir>] [--format=json|text]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Report produced. Always `0` on a non-error run — this tool never fails a build; a low completeness score is reported, not a failure exit. |
| `1` | A hard-fail `spec-linter` finding was present (R-ASSIST-001) — reported, not blocking anything outside this CLI invocation itself. |
| `2` | Usage error. |
