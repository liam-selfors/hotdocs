# CLI

```
hotdocs spec check <target>... [--model=<model>] [--write-proposals] [--strict]
    [--format=json|text] [--repo-root=<dir>]
```

`main(argv)` receives the tokens after `spec check`: `hotdocs-cli` strips
both verb words. `<target>` is a component id or criterion id, one or
more. `--repo-root` defaults to the current directory.

`--format=json` prints `ReviewReport.to_dict()` as one JSON document.
`--format=text`, the default, prints one line per finding and per gap,
`<criterion_id>: <kind>: <message or missing>`, then for each gap an
indented `propose: <proposed_text> (in <target_file>)` line, then a
summary line `<n> criteria checked, <f> findings, <g> gaps`.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | The check ran. Findings and gaps are advisory and do not change the code unless `--strict` is given. |
| `1` | A lint finding of `fail` severity in a named component, so criteria could not be checked; or, with `--strict`, any finding or gap. |
| `2` | Usage error, including an unknown target id, per `specs/architecture/cli-conventions.md`. |
