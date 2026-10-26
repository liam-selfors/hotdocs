# CLI

```
hotdocs provenance check <component-id> --spec-bundle-hash=<h> --gate-versions=<json> [--repo-root=<dir>] [--format=json|text]
```

Reports hit/miss for the given component and hash, same shape and
intent as `cache-manager`'s own `hotdocs cache inspect` — a developer
debugging why a merge did or didn't skip a component can check this
directly, without staging a merge.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Command completed (a reported "miss" is still exit `0` — it's an answer, not a failure). |
| `2` | Usage error (malformed hash, unknown component id). |
