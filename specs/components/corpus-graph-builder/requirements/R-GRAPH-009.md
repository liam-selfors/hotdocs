# R-GRAPH-009

**R-GRAPH-009** — Nodes and edges (R-GRAPH-001/002), the orphan rates
  (R-GRAPH-004/005) and size status MUST be computed from
  `graph-query-engine`'s shared `nodes`, `edges` and `component_size`
  views, never a third, independently written graph-construction step
  or word count (`D13`). Only the per-node verification and provenance
  are read from each manifest file itself, since a view's typed columns
  are not the file's JSON (`D200`).
