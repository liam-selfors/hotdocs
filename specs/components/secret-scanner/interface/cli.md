# CLI

```
hotdocs secret-scan [--repo-root=<dir>] [--format=json|text]
hotdocs secret-scan precommit [--files=<path>]... [--repo-root=<dir>] [--format=json|text]
```

- First form — full scan of `specs/`, `gen/`, and `verification/`, the
  merge-gate invocation (R-SECRET-001–007, cache-aware).
- `precommit` — lightweight invocation (R-SECRET-008), scoped to
  `--files` (defaults to the files staged/pending in the local git state
  when omitted: the union of `git diff --name-only --diff-filter=ACMR
  HEAD` and `git diff --cached --name-only --diff-filter=ACMR`, run in
  `--repo-root`; no files if `git` fails); no `cache-manager`
  dependency.

`main(argv)` receives the arguments after the `secret-scan` verb; a
leading `secret-scan` token, if present, is ignored. Every flag takes
its value either as `--flag=value` or as the next argument. `--files`
is repeatable, one path each; a relative `--files` path resolves
against `--repo-root`. `--repo-root` defaults to the current
directory, `--format` to `text`. `--format=json` prints the
`SecretScanResult` as JSON; `text` prints `CLEAN` or `FLAGGED` and one
line per match. A flag given last with no value, an invalid
`--format`, an unknown argument, or an unknown subcommand is a usage
error.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Clean. |
| `1` | Flagged — merge blocked (full-scan form) or commit/push should be stopped (precommit form). |
| `2` | Usage error. |
