# R-SCENARIO-002

**R-SCENARIO-002** — The capability-intersection lookup (`R-SCENARIO-001`)
  MUST query the `edges` view (`specs/architecture/
  graph-query-engine.md`), already shared by `impact-analyzer`/
  `spec-linter`/`corpus-graph-builder`, not a bespoke intersection:
  `SELECT DISTINCT target_id FROM edges WHERE edge_type = 'realizes' AND
  source_id IN (<blast-radius ids>)`. Implementation requirement only —
  `R-SCENARIO-001`'s behavior is unchanged.
