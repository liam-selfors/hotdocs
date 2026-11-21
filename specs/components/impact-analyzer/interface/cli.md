# CLI

```
hotdocs impact --changed <spec-id>... [--repo-root=<dir>] [--format=json|text]
```

- `--changed <spec-id>...` — one or more spec ids known to have changed in
  this diff (as determined by the caller, e.g. from `git diff`'s changed
  paths resolved to spec ids). Required, ≥1. `--changed` takes every
  following token up to the next one starting with `-`;
  `--changed=<id>` takes `<id>`, and may be followed by more ids the
  same way. `--changed` may be repeated; the ids accumulate. Any other
  token not starting with `-` is an unknown argument.
- `--repo-root` — defaults to the current git repository root.
- `--format` — `text` (human-readable, default) or `json` (the
  `BlastRadiusReport` schema below).

`--repo-root` and `--format` each accept `--flag=value` and
`--flag value`; the other usage errors are those
`specs/architecture/cli-conventions.md` lists.

**Text output.** One line per `impacted` entry, in report order:
`<component_id>`, a tab, `<reason>`; then, when `via` is non-null, a tab
and `via <via>`; then, for `transitive-guarantee`, a tab and the
`guarantee_ids` joined by `,`. With no entries the one line is
`no components impacted`; with a precondition error it is
`precondition error: <precondition_error>`. JSON output is the report
alone.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Blast radius computed successfully (may be empty if nothing depends on the changed ids and none are themselves components). |
| `1` | Precondition failure — the corpus did not pass `spec-linter` cleanly (R-IMPACT-007). |
| `2` | Usage error (no `--changed` ids given, an id that doesn't exist in the corpus at all). |
