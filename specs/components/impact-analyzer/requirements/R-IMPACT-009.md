# R-IMPACT-009

**R-IMPACT-009** — The corpus graph this component walks MUST be the
  `nodes`/`edges` views named in `specs/architecture/
  graph-query-engine.md`'s "Query surface" section — not a
  separately-written frontmatter load, and not a second definition of
  what counts as a node or edge. Those views already resolve every kind
  this component needs, guarantee nodes included. Transitive
  propagation (R-IMPACT-003/004/005/008) MUST be expressed as
  graph-pattern queries (DuckDB's `duckpgq` extension, per `MATCH` syntax)
  over `edges`.
