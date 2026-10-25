# R-LINT-020

**R-LINT-020** — R-LINT-003 (reference resolution), R-LINT-004 (acyclic
  `depends_on`), and R-LINT-018 (`depends_on_guarantees` resolution) MUST
  be implemented as queries over the `nodes`/`edges` views named in
  `specs/architecture/graph-query-engine.md`'s "Query surface" section —
  the same views `impact-analyzer` builds its graph from (R-IMPACT-009) —
  not independently-written frontmatter parsing or traversal code. This
  component already has to validate the graph is well-formed *before*
  `impact-analyzer` trusts it (R-IMPACT-007), so sharing the construction
  step means one ingestion bug surfaces identically in both places
  instead of two parsers silently disagreeing about what the graph is.

  This is an implementation requirement, not a behavioral one — it does
  not change what R-LINT-003/004/018 require the answer to be, only how
  the graph they check is built. R-LINT-018's second check (the resolved
  guarantee's owning component must already be in `depends_on`) becomes a
  plain join against `nodes.owner_component_id`, which exists precisely
  so this check doesn't need its own path-parsing.

  Out of scope: R-LINT-008/009 (requirement-to-acceptance traceability)
  walk a different graph — `R-id`/`AC-id` nodes joined by each acceptance
  file's `Covers:` tag, which is prose, not a frontmatter field — and are
  explicitly not covered here (see `graph-query-engine.md`'s "Scope of
  adoption" for why this is a distinct, not-yet-made decision rather than
  an oversight).
