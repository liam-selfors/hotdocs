# R-IMPACT-009

**R-IMPACT-009** — The corpus graph this component walks (nodes: spec ids;
  edges: `depends_on`, `realizes`, `uses_var`, `depends_on_guarantees`)
  MUST be built via the engine named in `specs/architecture/
  graph-query-engine.md`: frontmatter loaded directly from
  `specs/components/*/component.md`, `specs/product/*.md`, and
  `specs/vars/*.md` (DuckDB's `yaml` extension, `read_yaml_frontmatter()`
  — no intermediate file, no restructuring of those files' existing
  layout), with transitive propagation (R-IMPACT-003/004/005/008)
  expressed as graph-pattern queries (DuckDB's `duckpgq` extension) over
  that loaded data.

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
