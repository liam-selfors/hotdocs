# R-SCENARIO-001

**R-SCENARIO-001** — Given a blast-radius component-id set, MUST determine
  every product capability whose `realizes`-set intersects it
  (`R-SCENARIO-002`) and run each one's capability scenarios against the
  real, fully assembled `gen/` output — not a prediction, the actual
  regenerated system. Each capability scenario MUST be dispatched by its
  declared `kind` using exactly the same mechanisms already wired for
  `verifier-orchestrator` (`criterion-compiler` for `compiled`,
  `test_author` for `generated-test`, `judge` for `llm-judge`) — no new
  dispatch machinery.

  The result (`CapabilityScenarioReport`) MUST carry one entry **per
  scenario**, not one aggregate verdict per capability — a capability
  with more than one scenario MUST be able to show which specific one
  failed, the same granularity `VerificationReport.criteria[]` already
  gives per-criterion. Each entry's `result` an `llm-judge` dispatch
  produced MUST carry a `rationale` alongside it, per `SPEC_GUIDELINES.md`
  §5's existing, general rule ("An `llm-judge` criterion MUST emit
  structured rationale alongside its verdict") — this report is not a
  special case exempt from a rule every other `llm-judge`-dispatching
  result in this corpus already follows.

  The whole report MUST be keyed by `P-id`, a distinct namespace from
  any single component's own verification result — this is a
  cross-component finding, never attributable to one component, and
  `merge-orchestrator` (`R-MERGE-011`) relies on that distinction to
  report it separately.
