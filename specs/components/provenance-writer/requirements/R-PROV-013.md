# R-PROV-013

**R-PROV-013** — `verification_run_id` MUST be deterministically
  constructed from `ProvenanceInputs.component_id` (slug) and
  `ProvenanceInputs.attempts` as `"<slug>-attempt-<attempts>"` — never
  a freshly generated random value (`D67`).
