# CLI

```
hotdocs track ui build [--changed=<id>...] [--repo-root=<dir>] [--out=<dir>] [--model=<model>] [--seed=<n>]
```

`main(argv)` receives `argv` beginning `["track", "ui", "build", ...]`.
Every flag takes its value either as `--flag=value` or as the next
argument (`--flag value`); a flag given last with no value, a
non-integer `--seed`, or `argv` not beginning with those three words is
a usage error.

- `--changed` — repeatable, or comma-separated; omitted means the
  whole-corpus view (`R-UI-007`).
- `--out` — output directory. Default: `.hotdocs/ui/` — local-only, the
  same as the tracking data it renders (`SPEC_GUIDELINES.md` §1), never
  `dist/`: unlike `docs-site-renderer`'s output, this page is never
  published.
- `--model`/`--seed` — passed straight through to `check_readiness`
  (`D154`), only consulted if a capability in scope is a provenance
  miss.

Prints the path of the written `index.html`, which opens directly from
`file://` (`R-UI-006`).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Page written — including when `.hotdocs/attempts/` is empty or missing (`R-UI-005`). |
| `1` | A file that exists failed to parse as JSON (`corpus-graph.json`, or an `AttemptRecord`). |
| `2` | Usage error — bad arguments, a missing `corpus-graph.json`, or `provenance-tracker`'s own `UsageError` (a capability miss with no `--model`). |
