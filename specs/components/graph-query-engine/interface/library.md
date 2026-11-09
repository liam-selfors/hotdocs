# Library

```
load_views(con: duckdb.DuckDBPyConnection, repo_root: Path) -> None
```

Creates (or replaces) all seven views — `nodes`, `edges`,
`component_docs`, `component_context`, `component_provenance`,
`component_size`, `decision_lineage` — on `con`, scoped to the spec corpus under
`repo_root`. Requires the `yaml` community extension be installed and
loaded on `con` before calling (this component does not install it
itself) — **literally `INSTALL yaml FROM community` then
`LOAD yaml`, never a bare `INSTALL yaml`** (`D135`): a bare install
defaults to a different extension registry than the community one,
and conflicts outright on any machine where the community-origin
extension is already cached from a prior install, raising rather than
silently reusing it. `duckpgq` is not required by these views themselves —
none of them use its `MATCH` syntax — but a consumer MAY load it
separately to run its own traversal queries against the resulting
`nodes`/`edges` tables (see `specs/architecture/
graph-query-engine.md` for why these two extensions specifically).

Implements: `specs/architecture/graph-query-engine.md`
