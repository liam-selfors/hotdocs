# R-GOLDEN-002

**R-GOLDEN-002** — The capability-intersection lookup (`R-GOLDEN-001`)
  MUST query the `edges` view (`specs/architecture/
  graph-query-engine.md`), already shared by `impact-analyzer`/
  `spec-linter`/`corpus-graph-builder`, not a bespoke intersection:
  `SELECT DISTINCT target_id FROM edges WHERE edge_type = 'realizes' AND
  source_id IN (<blast-radius ids>)`. Implementation requirement only —
  `R-GOLDEN-001`'s behavior is unchanged.
