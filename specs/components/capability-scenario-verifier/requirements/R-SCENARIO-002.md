# R-SCENARIO-002

**R-SCENARIO-002** — The capability-intersection lookup
  (`R-SCENARIO-001`) MUST be one query against the shared `edges` view
  (`specs/architecture/graph-query-engine.md`), not a bespoke
  intersection: `SELECT DISTINCT target_id FROM edges WHERE edge_type =
  'realizes' AND source_id IN (<blast-radius ids>)`.

  **`realizes` is declared per component, never per capability**
  (`D61`): it is the `realizes:` frontmatter field of a component's own
  `component.md`. No `specs/product/<name>.md` carries one. Without
  `graph-query-engine` as a dependency, the equivalent edge set is
  built by scanning every `specs/components/*/component.md`.

  A capability's **realizing set** is every component whose `realizes`
  names it. A component's **code directory** is `gen/<slug>/`, or, when
  it is `sealed: true`, its frontmatter `source_path`, both under
  `repo_root`. Both are used by `R-SCENARIO-005` and `R-SCENARIO-006`.
