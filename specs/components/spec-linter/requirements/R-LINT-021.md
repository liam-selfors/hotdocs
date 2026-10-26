# R-LINT-021

**R-LINT-021** — R-LINT-008 (forward traceability) and R-LINT-009
  (backward traceability) MUST be implemented as queries over the
  `nodes`/`edges` views named in `specs/architecture/
  graph-query-engine.md`'s "Query surface" section, extended there with
  `requirement`/`acceptance`/`capability_scenario` node kinds and the
  `covers` edge type (D27) — not independently-written traversal code.
  See that document's "Scope of adoption" section for the full
  rationale.

  R-LINT-008 becomes: every `requirement` node MUST be the target of at
  least one `covers` edge. R-LINT-009 becomes: every `covers` edge's
  target MUST resolve to a real `requirement` or `capability` node, and
  (per its existing distinct-message behavior) report separately whether
  a non-resolving target looked like an `R-id`, a `P-id`, or neither.

  Implementation requirement, not a behavioral one: neither rule's
  actual check changes.

  Exception (D44): R-LINT-009's own iteration and reported line number
  stay a native `_collect_covers` scan over each `component-acceptance`/
  `product` doc's body — `nodes`/`edges` resolve whether a `Covers:`
  target exists, but don't model which `product` doc owns a given
  `CS-id` (`R-GQE-001` leaves `capability_scenario` rows' owner
  deliberately unset — the `covers` edge carries that relationship, not
  a reverse lookup), so there is no view-only path back to the right
  doc and line to report against.
