# R-MERGE-020

**R-MERGE-020** — R-MERGE-014's capability-intersection lookup MUST query
  the `edges` view (`specs/architecture/graph-query-engine.md`), already
  shared by `impact-analyzer`/`spec-linter`/`corpus-graph-builder`, not a
  bespoke intersection: `SELECT DISTINCT target_id FROM edges WHERE
  edge_type = 'realizes' AND source_id IN (<blast-radius ids>)`.
  Implementation requirement only — R-MERGE-014's gate behavior is
  unchanged.
