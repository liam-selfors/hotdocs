# CLI

```
hotdocs decision new <title> [--owners=<a,b>] [--builds-on=<D1,D2>] [--supersedes=<D<N>>] [--repo-root=<dir>]
hotdocs decision ratify <D<N>> [--repo-root=<dir>]
hotdocs decision record-commit <D<N>> [--commit=<hash>] [--repo-root=<dir>]
hotdocs component new <slug> [--title=<title>] [--owners=<a,b>] [--depends-on=<comp-a,comp-b>]
    [--realizes=<P-a,P-b>] [--sealed] [--repo-root=<dir>]
```

`main(argv)` receives `argv` beginning `["decision", ...]` or
`["component", ...]`: `hotdocs-cli` strips no words for these verbs.
`--repo-root` defaults to the current directory. Comma-separated flag
values are split on `,` with surrounding spaces removed.

On success each command prints one line to stdout and returns `0`:

- `decision new`: the path written, relative to `repo_root`
  (`specs/decisions/D13.md`).
- `decision ratify`: each path changed, one per line, the record first
  and then any record it supersedes.
- `decision record-commit`: the commit recorded.
- `component new`: the directory written, relative to `repo_root`
  (`specs/components/my-thing/`).

A `ValueError`, `FileExistsError` or `LookupError` from the library prints
one line, `error: <message>`, to stderr and returns `1`. Usage errors
follow `specs/architecture/cli-conventions.md` and return `2`.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | The file or directory was written. |
| `1` | The library refused: invalid argument, existing target, or unknown, already-ratified, unratified or uncommitted decision. |
| `2` | Usage error. |
