# CLI

```
hotdocs lint [<path>...] [--format=json|text] [--strict] [--repo-root=<dir>]
```

`main(argv: list[str] | None = None) -> int` gets the tokens after `lint`
(`hotdocs-cli` strips the verb) and returns the exit code; `python -m
spec_linter` passes `sys.argv[1:]`.

- `<path>...` — files or directories under `specs/` to lint; default the
  whole `specs/` tree.
- `--format` — `text` (default) or `json` (a `LintReport`).
- `--strict` — `warn` findings count as failures too.
- `--repo-root` — the repository root; default the current git
  repository's.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | No `fail`-severity findings (`skipped` never fails). |
| `1` | ≥1 `fail`-severity finding. |
| `2` | Usage error (bad arguments, unreadable path). |
