# CLI

```
hotdocs provenance check <component-id> --spec-bundle-hash=<h> --gate-versions=<json> [--repo-root=<dir>] [--format=json|text]
```

Reports hit/miss for the given component and hash, for a developer
debugging why a component did or didn't skip regeneration.

`main(argv)` receives `argv` beginning `["check", ...]` (the
`provenance` verb is already consumed). Every flag takes its value
either as `--flag=value` or as the next argument. `--gate-versions` is
a JSON object of strings. `--repo-root` defaults to the current
directory, `--format` to `text`. `--format=json` prints the
`ProvenanceCheckResult` as JSON; `text` prints `hit` or `miss` and the
component id. A missing `<component-id>`, `--spec-bundle-hash`, or
`--gate-versions`; a `<component-id>` not of the form `comp-<slug>`
or `<slug>` (lowercase letters, digits, single hyphens); a
`--spec-bundle-hash` not of the form `sha256:` followed by one or more
lowercase hex digits; `--gate-versions` that is not a JSON object of
strings to strings; an
invalid `--format`; an unknown argument or subcommand; or a flag given
last with no value is a usage error.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Command completed (a reported "miss" is still exit `0` — it's an answer, not a failure). |
| `2` | Usage error. |
