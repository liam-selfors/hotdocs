# R-ASSEMBLE-010

**R-ASSEMBLE-010** — For each id in the component's `depends_on`, the
  bundle MUST also include that component's `Purpose` section text,
  leading and trailing whitespace stripped, as `dependency_context[id]`, read via `component_context`
  (`specs/architecture/graph-query-engine.md`, `D22`) — never read
  directly from the dependency's `component.md` by this component's own
  logic, and never any other part of `component.md`.

  This is the single exception `R-ASSEMBLE-002` names (`D21`).
