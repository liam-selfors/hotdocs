# CLI

```
hotdocs corpus-graph build [--repo-root=<dir>]
```

`main` receives the tokens from `build` on, such as the list
`["build", "--repo-root=/x"]`. `--repo-root <dir>` is accepted too; the default is
the current directory. On success it writes the file and prints its
path.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | `verification/corpus-graph.json` written. |
| `1` | Building failed, e.g. a `.provenance.json` that is not valid JSON. |
| `2` | Usage error: no `build`, another word, or an unknown argument. |
