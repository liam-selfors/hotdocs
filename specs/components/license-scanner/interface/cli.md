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
including `similarity_score` and `blocked`, and, when `evaluated` is
`false`, a plain line `NOT EVALUATED: <reason>` with a hint to set
`VAR_LICENSE_CORPUS_PATH` for `no-reference-corpus`.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Not blocked: below the block threshold, or not evaluated for want of any corpus (`NOT EVALUATED: no-reference-corpus`). |
| `1` | Blocked: at or above the block threshold, or a configured corpus that is unreadable or invalid (`R-LICENSE-011`). |
| `2` | Usage error. |
