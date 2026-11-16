# R-ASSEMBLE-002

**R-ASSEMBLE-002** — For each id in the component's `depends_on`, the
  bundle MUST include that component's `interface/` content only — never
  its `requirements/` or `constraints.md`, and never any part of its
  `component.md` except the single, narrow exception `R-ASSEMBLE-010`
  names. A dependent needs the contract, not the internal rationale;
  this is the same interface-vs-internal distinction `impact-analyzer`
  already established for blast-radius propagation (R-IMPACT-002/003),
  applied here to what a dependent is allowed to *see*, not just what
  triggers its regeneration.
