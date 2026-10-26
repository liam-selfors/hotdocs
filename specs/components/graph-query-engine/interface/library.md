# Library

```
load_views(con: duckdb.DuckDBPyConnection, repo_root: Path) -> None
```

Creates (or replaces) all six views — `nodes`, `edges`,
`component_docs`, `component_context`, `component_provenance`,
`component_size` — on `con`, scoped to the spec corpus under
`repo_root`. Requires the `yaml` community extension be installed and
loaded on `con` before calling (this component does not install it
itself). `duckpgq` is not required by these six views themselves —
none of them use its `MATCH` syntax — but a consumer MAY load it
separately to run its own traversal queries against the resulting
`nodes`/`edges` tables (see `specs/architecture/
graph-query-engine.md` for why these two extensions specifically).
