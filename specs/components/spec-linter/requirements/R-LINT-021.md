# R-LINT-021

**R-LINT-021** — R-LINT-008 (forward traceability) and R-LINT-009
  (backward traceability) MUST be implemented as queries over the
  `nodes`/`edges` views named in `specs/architecture/
  graph-query-engine.md`'s "Query surface" section — the same views
  `impact-analyzer`, `corpus-graph-builder`, and `golden-scenario-
  verifier` already query, extended there with `requirement`/
  `acceptance`/`golden_scenario` node kinds and the `covers` edge type
  (D27) — not independently-written traversal code.

  R-LINT-008 becomes: every `requirement` node MUST be the target of at
  least one `covers` edge. R-LINT-009 becomes: every `covers` edge's
  target MUST resolve to a real `requirement` or `capability` node, and
  (per its existing distinct-message behavior) report separately whether
  a non-resolving target looked like an `R-id`, a `P-id`, or neither.

  This is an implementation requirement, not a behavioral one — neither
  rule's actual check changes. `golden_scenario` and `acceptance` nodes
  are modeled for graph completeness; neither rule's own logic needs
  them as addressable nodes to resolve against (R-LINT-008 only counts
  edges per `requirement`; R-LINT-009 only validates edge targets against
  `requirement`/`capability` nodes) — only the `covers` edges
  originating from them matter here.
