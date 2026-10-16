# CLI

```
hotdocs lint [<path>...] [--format=json|text] [--strict] [--repo-root=<dir>]
```

- `<path>...` — one or more files or directories under `specs/` to lint.
  Defaults to the whole `specs/` tree.
- `--format` — `text` (human-readable, default) or `json` (the `LintReport`
  schema below).
- `--strict` — treat `warn`-severity findings as failures too.
- `--repo-root` — repository root, for resolving the corpus and
  `specs/glossary.md`. Defaults to the current git repository root.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | No `fail`-severity findings (warnings and `skipped` findings may be present, even under `--strict` — `skipped` is never promoted to a failure; it means "not evaluated," not "passed" or "violated"). |
| `1` | ≥1 `fail`-severity finding. |
| `2` | Usage error (bad arguments, unreadable path). |
