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

  `read_yaml_frontmatter` MUST NOT be allowed to raise merely because a
  glob it reads matches zero files (unlike `read_text`, which already
  tolerates this natively — confirmed by hand, not assumed): a corpus
  legitimately has no `specs/vars/*.md` or `specs/product/*.md` files
  yet in some states (`graph-query-engine`'s own sparse test fixtures,
  `spec-linter`'s, D44), and that is expected state, not an error, the
  same posture `R-GQE-005` already requires for zero `.provenance.json`
  files. `load_views` MUST pre-check each such glob and substitute a
  typed, always-empty relation for that one call site when it has zero
  matches, rather than letting the bind-time error propagate.
  `specs/components/*/component.md` is deliberately exempt from this
  guard — no corpus is ever linted with zero components in it.
