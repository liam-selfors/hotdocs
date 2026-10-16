# CLI

```
hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]
```

- `--out` — output directory for the rendered static site. Default:
  `dist/docs-site/` (a build artifact location, not `gen/` — this
  component's output is never committed, per D9/R-DOCS-005).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Site rendered to `--out`. |
| `1` | `corpus-graph.json` missing or unreadable. |
| `2` | Usage error. |
