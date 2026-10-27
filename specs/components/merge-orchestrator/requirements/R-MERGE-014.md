# R-MERGE-014

**R-MERGE-014** — Once every component in the blast radius has regenerated
  and passed its own per-component verification (R-MERGE-004–009 for all
  of them, not just one), MUST call `capability-scenario-verifier` with
  the full blast-radius component-id set, wiring the same real `judge`
  and `test_author` callables R-MERGE-004 wires into
  `verifier-orchestrator`'s call, and incorporate its
  `CapabilityScenarioReport` into `MergeResult.capability_scenarios` (a
  distinct result category from any single component's own
  verification, never conflated with it) and the overall block decision
  (R-MERGE-011).

  This is the backstop for cross-component behavioral risk that no amount
  of `interface/`-level diffing can rule out in principle (D2) — a
  **permanent** gate, not superseded once `interface/guarantees/` (D2)
  makes more of the contract explicit, because documentation of
  foreseeable guarantees can never be complete. The dispatch mechanics
  themselves (capability-intersection lookup, `kind`-based dispatch) are
  `capability-scenario-verifier`'s own job (`R-SCENARIO-001`/`002`,
  D14) — this requirement is about *when* and *with what* it gets called,
  not how it runs.
