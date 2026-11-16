# R-LINT-020

**R-LINT-020** — R-LINT-003 (reference resolution), R-LINT-004 (acyclic
  `depends_on`), and R-LINT-018 (`depends_on_guarantees` resolution) MUST
  be implemented as queries over the `nodes`/`edges` views named in
  `specs/architecture/graph-query-engine.md`'s "Query surface" section —
  not independently-written frontmatter parsing or traversal code.

  Implementation requirement, not behavioral: R-LINT-018's second check
  is a join against `nodes.owner_component_id`. R-LINT-008/009 are
  `R-LINT-021`'s.

  Exception (D13): `nodes`/`edges` are component-level only, so
  R-LINT-003/004 each keep one native residual check for `architecture`-
  doc `depends_on` (grep-confirmed, the one other doc_type with any).
