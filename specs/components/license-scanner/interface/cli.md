# CLI

```
hotdocs license-scan <component-id> [--repo-root=<dir>] [--format=json|text]
```

`main(argv)` receives `argv` beginning with `<component-id>` (the
`license-scan` verb is already consumed). Every flag takes its value
either as `--flag=value` or as the next argument; a flag given last
with no value, a missing `<component-id>`, an invalid `--format`, or
an unknown argument is a usage error. `--repo-root` defaults to the
current directory, `--format` to `text`. `--format=json` prints the
`LicenseScanResult` as JSON; `text` prints a human-readable summary
including `similarity_score` and `blocked`.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Clean (below block threshold). |
| `1` | Flagged (at or above block threshold) — merge blocked. |
| `2` | Usage error. |
