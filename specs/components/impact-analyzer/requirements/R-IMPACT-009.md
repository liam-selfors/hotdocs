# R-IMPACT-009

**R-IMPACT-009** — The corpus graph this component walks MUST be the
  `nodes`/`edges` views named in `specs/architecture/
  graph-query-engine.md`'s "Query surface" section — not a
  separately-written frontmatter load, and not a second definition of
  what counts as a node or edge. Those views already resolve every kind
  this component needs, guarantee nodes included (via `read_text()` over
  `interface/guarantees/*.md`, since those files carry no frontmatter to
  extract — `read_yaml_frontmatter()` alone cannot see them). Transitive
  propagation (R-IMPACT-003/004/005/008) MUST be expressed as
  graph-pattern queries (DuckDB's `duckpgq` extension, per `MATCH` syntax)
  over `edges`.

  This is an implementation requirement, not a behavioral one — it
  constrains *how* the graph is built and traversed, not *what*
  R-IMPACT-001 through R-IMPACT-008 require the answer to be. Rebuilt on
  this engine or not, this component still owes the exact same
  `BlastRadiusReport` for the same inputs; R-IMPACT-006's purity
  requirement is unaffected (DuckDB is embedded and local — no network
  access, no model calls, fully deterministic given the same input
  files) and is, if anything, strengthened: the graph construction and
  traversal steps are now backed by a maintained query engine instead of
  bespoke traversal code written once for this component alone.
