# CLI

```
hotdocs secret-scan [--repo-root=<dir>] [--format=json|text]
hotdocs secret-scan precommit [--files=<path>]... [--repo-root=<dir>] [--format=json|text]
hotdocs secret-scan propose [--repo-root=<dir>]
```

- First form — full, cache-aware scan of the whole repository (`R-SECRET-001`–`007`).
- `precommit` — lightweight invocation (`R-SECRET-008`), scoped to
  `--files` (defaults to the files staged/pending in the local git
  state when omitted: the union of `git diff --name-only
  --diff-filter=ACMR HEAD` and `git diff --cached --name-only
  --diff-filter=ACMR`, run in `--repo-root`; no files if `git` fails);
  no `cache-manager` dependency. A relative `--files` path resolves
  against `--repo-root`.
- `propose` — prints an `AllowlistProposal` as JSON (`R-SECRET-013`);
  accepts no `--format`.

`main(argv)` receives the arguments after the `secret-scan` verb (a
leading `secret-scan` token is ignored). Every flag takes its value as
`--flag=value` or as the next argument; `--files` is repeatable.
`--repo-root` defaults to the current directory, `--format` to `text`.
`json` prints the `SecretScanResult`; `text` prints `CLEAN` or
`FLAGGED` and one line per match. A flag last with no value, an invalid
`--format`, an unknown argument, or an unknown subcommand is a usage
error.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Clean; or, for `propose`, every finding can be allowlisted. |
| `1` | Flagged — merge blocked (full-scan form) or commit/push should be stopped (precommit form); for `propose`, at least one finding is `ineligible`. |
| `2` | Usage error; for `propose`, also an invalid allowlist. |
