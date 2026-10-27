# R-PROV-013

**R-PROV-013** — `verification_run_id` MUST be deterministically
  constructed from `ProvenanceInputs.component_id` (slug) and
  `ProvenanceInputs.attempts` as `"<slug>-attempt-<attempts>"` — never
  a freshly generated random value (`D83`, found previously
  unsourced). `constraints.md`'s determinism requirement (byte-identical
  output given the same input) already forbids a random id; this makes
  the specific construction explicit rather than leaving it to be
  independently guessed.
