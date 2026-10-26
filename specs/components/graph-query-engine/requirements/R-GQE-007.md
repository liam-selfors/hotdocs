# R-GQE-007

**R-GQE-007** — MUST expose a `load_views(con, repo_root)` call that
  creates all six views (`R-GQE-001`–`006`) against a given DuckDB
  connection, substituting `repo_root` (an absolute path) for every
  `{repo_root}` placeholder in the generated SQL before executing each
  `CREATE VIEW` statement in dependency order (`component_context`
  after `component_docs`, since it selects from it). Idempotent: MUST
  NOT fail if called twice on the same connection (`CREATE OR REPLACE
  VIEW`, not bare `CREATE VIEW`). MUST raise, not swallow, any error a
  view's own `CREATE VIEW` statement raises — a caller needs to know
  immediately if a view it depends on failed to create, not discover
  it later as a missing-table error on first query.
