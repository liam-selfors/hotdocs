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

  Exception, confirmed by corpus-wide grep before being relied on (D44):
  `nodes`/`edges` are scoped to component-level data only (per
  `graph-query-engine`'s own "Query surface" section), so R-LINT-003's
  and R-LINT-004's `depends_on` checks each retain one small, explicit,
  native-Python residual check for `architecture`-doc-type frontmatter —
  the one other `FRONTMATTER_BEARING_TYPES` doc_type in this corpus with
  a real non-empty `depends_on` (`specs/architecture/
  pipeline-decomposition.md`); `product`/`var`/`decision` docs never
  populate `depends_on`/`realizes`/`uses_var`, so they need no such
  exception, and R-LINT-018's `depends_on_guarantees` has no architecture
  usage at all.
