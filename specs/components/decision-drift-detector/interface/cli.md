# CLI

```
hotdocs decision-drift [--format=json|text] [--repo-root=<dir>]
hotdocs decision-impact <decision-id> [--format=json|text] [--repo-root=<dir>]
```

- `--format` — `text` (human-readable, default) or `json` (the
  `DriftReport`/`DecisionImpactReport` schema, matching whichever
  subcommand ran).
- `--repo-root` — repository root. Defaults to the current git
  repository root.
- `<decision-id>` (`decision-impact` only) — the `D<N>` being
  considered for alteration or supersession. Need not resolve to a
  real file yet.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Ran successfully, report produced (an empty report is a clean result, not an error). |
| `2` | Usage error (not a git repository, unreadable path, missing `<decision-id>` for `decision-impact`). |
