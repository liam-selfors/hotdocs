# R-MERGE-014

**R-MERGE-014** — Once every component in the blast radius has regenerated
  and passed its own per-component verification (R-MERGE-004–009 for all of
  them, not just one), MUST run the golden scenarios of every product
  capability whose `realizes`-set intersects the blast radius, against the
  real, fully assembled `gen/` output produced by this merge — not a
  prediction, the actual regenerated system. Each golden scenario MUST be
  dispatched by its declared `kind` using exactly the same mechanisms
  already wired for `verifier-orchestrator` in R-MERGE-004 (`criterion-
  compiler` for `compiled`, `test_author` for `generated-test`, `judge` for
  `llm-judge`) — no new dispatch machinery. A failure here MUST be recorded
  as a distinct result from any single component's verification result
  (this is a cross-component finding, not attributable to one component)
  and MUST count toward the overall block decision (R-MERGE-011). This is
  the backstop for cross-component behavioral risk that no amount of
  `interface/`-level diffing can rule out in principle (D16) — a
  **permanent** gate, not superseded once `interface/guarantees/` (D16)
  makes more of the contract explicit, because documentation of foreseeable
  guarantees can never be complete.
