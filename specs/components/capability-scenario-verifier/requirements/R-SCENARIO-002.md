# R-SCENARIO-002

**R-SCENARIO-002** — The capability-intersection lookup (`R-SCENARIO-001`)
  MUST query the `edges` view (`specs/architecture/
  graph-query-engine.md`), already shared by `impact-analyzer`/
  `spec-linter`/`corpus-graph-builder`, not a bespoke intersection:
  `SELECT DISTINCT target_id FROM edges WHERE edge_type = 'realizes' AND
  source_id IN (<blast-radius ids>)`. Implementation requirement only —
  `R-SCENARIO-001`'s behavior is unchanged.

  **`realizes` edges are declared per-component, never per-capability**
  (`D77`, found wrong twice in a row without this): the `realizes:`
  frontmatter field lives on a *component's* own `component.md` (e.g.
  `specs/components/cache-manager/component.md`'s `realizes:
  [P-ZERO-EDIT]`), naming the capabilities that component realizes —
  `source_id` in the SQL above. No product-capability file
  (`specs/product/<name>.md`) ever carries a `realizes:` field itself;
  scanning capability files for one, as if the edge were declared
  there, will always find nothing. Without `comp-graph-query-engine` as
  a real dependency, building the equivalent `realizes` edge set
  locally means scanning every `specs/components/*/component.md` for
  its own `realizes:` list — the same direction `impact-analyzer`'s own
  `R-IMPACT-005` already establishes for this exact field, just not
  visible from this component's own bundle, which doesn't depend on
  `impact-analyzer`.
