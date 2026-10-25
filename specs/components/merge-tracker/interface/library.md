# Library

```
write_tracking_record(
    changed_ids: list[str],
    component_ids: list[str],
    block_reasons: list[str],
    overall: str,
    repo_root: Path,
) -> TrackingRecord
```

`component_ids` is the full impacted set for this attempt (from
`impact-analyzer`'s blast radius) — this component reads each one's
already-written `ProvenanceInputs`-derived manifest from
`provenance-writer`'s output on disk (R-TRACK-004) rather than receiving
per-component detail as a parameter. `overall` is `"pass"` or `"blocked"`.
Writes the record to `.hotdocs/tracking/` (R-TRACK-003) and returns it.

```
query_recent(repo_root: Path, limit: int = 50, component_id: str | None = None) -> list[TrackingRecord]
```

A thin convenience wrapper over `SELECT * FROM
read_json('.hotdocs/tracking/*.json') ORDER BY timestamp DESC LIMIT
?` (optionally filtered to one component) — not a second implementation
of anything, just this component saving a caller from typing the query
by hand (R-TRACK-006).
