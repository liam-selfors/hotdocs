# R-ASSEMBLE-010

**R-ASSEMBLE-010** — For each id in the component's `depends_on`, the
  bundle MUST also include that component's `Purpose` section text as
  `dependency_context[id]`, read via `component_context`
  (`specs/architecture/graph-query-engine.md`, `D35`) — never read
  directly from the dependency's `component.md` by this component's own
  logic, and never any other part of `component.md`.

  This is the single, explicit exception `R-ASSEMBLE-002` names, scoped
  to exactly `Purpose` and nothing else: `D34` made `Purpose`
  dependent-safe by construction (no decision citations, no historical
  rationale, enforced by `R-LINT-024`), which is what makes handing it
  to a dependent safe in the first place. If a future need arises to
  share more of a dependency's `component.md`, that is a new decision
  with its own safety argument — this requirement does not imply one.
