# CLI

```
hotdocs assemble <component-id> [--mode=cold|hint] [--repo-root=<dir>] [--format=json|text]
```

- `<component-id>` — the component's `spec.md` frontmatter `id`.
- `--mode` — `cold` (default; canonical bundle only) or `hint` (adds
  `hint_code`, R-ASSEMBLE-008).
- `--format` — `text` (summary) or `json` (the `SpecBundle` schema below).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Bundle assembled. |
| `1` | Precondition failure — corpus not lint-clean (R-ASSEMBLE-005). |
| `2` | Usage error (unknown component id, bad `--mode`). |
