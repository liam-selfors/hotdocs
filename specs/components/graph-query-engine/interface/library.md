# Library

```
load_views(con: duckdb.DuckDBPyConnection, repo_root: Path) -> None
```

Creates (or replaces) all eight views — `nodes`, `edges`,
`component_docs`, `component_context`, `component_provenance`,
`component_size`, `bundle_size`, `decision_lineage` — on `con`, scoped to the spec corpus under
`repo_root`. Requires the `yaml` community extension be installed and
loaded on `con` before calling (this component does not install it
itself) — **literally `INSTALL yaml FROM community` then
`LOAD yaml`, never a bare `INSTALL yaml`** (`D135`). `duckpgq` is not
required.

Implements: `specs/architecture/graph-query-engine.md`, `specs/architecture/graph-query-engine-fixture.md`
