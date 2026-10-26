# R-LINT-020

**R-LINT-020** — R-LINT-003 (reference resolution), R-LINT-004 (acyclic
  `depends_on`), and R-LINT-018 (`depends_on_guarantees` resolution) MUST
  be implemented as queries over the `nodes`/`edges` views named in
  `specs/architecture/graph-query-engine.md`'s "Query surface" section —
  not independently-written frontmatter parsing or traversal code. See
  that document's "Scope of adoption" section for the full rationale.

  Implementation requirement, not a behavioral one: does not change
  what R-LINT-003/004/018 require the answer to be. R-LINT-018's second
  check becomes a plain join against `nodes.owner_component_id`.
  R-LINT-008/009's own graph-query treatment is `R-LINT-021`'s, not
  this rule's.
