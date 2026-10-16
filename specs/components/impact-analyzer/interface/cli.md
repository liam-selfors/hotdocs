# CLI

```
hotdocs impact --changed <spec-id>... [--repo-root=<dir>] [--format=json|text]
```

- `--changed <spec-id>...` — one or more spec ids known to have changed in
  this diff (as determined by the caller, e.g. from `git diff`'s changed
  paths resolved to spec ids). Required, ≥1.
- `--repo-root` — defaults to the current git repository root.
- `--format` — `text` (human-readable, default) or `json` (the
  `BlastRadiusReport` schema below).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Blast radius computed successfully (may be empty if nothing depends on the changed ids and none are themselves components). |
| `1` | Precondition failure — the corpus did not pass `spec-linter` cleanly (R-IMPACT-007). |
| `2` | Usage error (no `--changed` ids given, an id that doesn't exist in the corpus at all). |
