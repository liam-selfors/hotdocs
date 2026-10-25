# CLI

```
hotdocs track query [--last=<n>] [--component=<spec-id>] [--repo-root=<dir>] [--format=json|text]
```

- `--last` — how many most-recent records to return. Default `10`.
- `--component` — filter to records mentioning this component id.
  Optional.
- `--repo-root` — defaults to the current git repository root.
- `--format` — `text` (human-readable, default) or `json`.

There is no `hotdocs track write` CLI command — writing is invoked by
`merge-orchestrator` directly (`write_tracking_record`, never run
standalone by a human), consistent with `R-TRACK-005`'s "not a gate,
not a user-facing step in its own right" posture. Querying is the only
user-facing surface this component adds; it exists purely for
convenience over running the equivalent DuckDB query by hand
(R-TRACK-006) — `.hotdocs/tracking/*.json` is always readable directly
by any DuckDB client, with or without this CLI.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Query ran (result may be empty if no records exist yet). |
| `2` | Usage error. |
