# R-IMPACT-012

**R-IMPACT-012** — A changed id naming a requirement (`R-…`) or an
  acceptance criterion (`AC-…`) MUST be resolved to the component whose
  `specs/components/<slug>/requirements/<id>.md` or
  `specs/components/<slug>/acceptance/<id>.md` exists, and that
  component is then a changed component exactly as if its own id had
  been given: it is in `impacted` with reason `direct` and `via` `null`,
  as every `direct` entry is, and `R-IMPACT-002`/`R-IMPACT-003` decide its dependents from
  what changed in its files (`D393`). Two ids of one component, or an id
  and the component's own id, give one entry. An `R-`/`AC-` id no component holds
  resolves to nothing, as before.
