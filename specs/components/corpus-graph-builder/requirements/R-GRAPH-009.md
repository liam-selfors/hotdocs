# R-GRAPH-009

**R-GRAPH-009** — R-GRAPH-001/002 (node/edge construction) MUST be built
  from the `nodes`/`edges` views named in `specs/architecture/
  graph-query-engine.md`'s "Query surface" section — the same views
  `impact-analyzer` (R-IMPACT-009) and `spec-linter` (R-LINT-020) use —
  not a third, independently-written graph-construction step.

  R-GRAPH-003's per-node annotations and R-GRAPH-004/005's corpus-wide
  orphan rates MUST be computed as joins and aggregates against
  `nodes`/`edges`/`component_provenance`/`component_size`, all four
  named in `specs/architecture/graph-query-engine.md`'s "Query surface"
  section — `component_provenance` is shared with `review-packet-builder`
  (R-PACKET-011, D26), `component_size` with `spec-linter`'s own
  `rule_size_caps` (`R-LINT-012`, `D42`). Neither is redefined here;
  this component MUST query the shared view, not maintain its own copy
  of either.

  This is an implementation requirement, not a behavioral one —
  R-GRAPH-001 through 008 are unaffected; R-GRAPH-006/008 (the committed,
  deterministic `verification/corpus-graph.json` output) are unchanged —
  only the graph- and annotation-*construction* steps move onto this
  engine, not the output format or its determinism obligation.
