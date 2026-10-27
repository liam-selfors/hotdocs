# CLI

```
hotdocs decision-drift [--format=json|text] [--repo-root=<dir>]
```

- `--format` — `text` (human-readable, default) or `json` (the
  `DriftReport` schema below).
- `--repo-root` — repository root. Defaults to the current git
  repository root.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Ran successfully, report produced (`entries` may be empty — that is a clean result, not an error). |
| `2` | Usage error (not a git repository, unreadable path). |

Always exits `0` on a successful run regardless of whether drift was
found — this is a diagnostic tool, not a gate; nothing about a
non-empty report is a failure to signal via exit code.
