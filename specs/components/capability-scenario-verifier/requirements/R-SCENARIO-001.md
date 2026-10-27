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

  **Where a capability's own scenarios live** (`D75`, found missing
  from this bundle's own visible text): there is no `specs/capabilities/`
  directory anywhere in this corpus. A `P-<id>`'s capability scenarios
  are `### CS-<id>` sections embedded directly inside that capability's
  own `specs/product/<name>.md` file (`SPEC_GUIDELINES.md` §3.1), each
  carrying its own `Covers:`/`Kind:`/Gherkin block — the exact same
  shape as a component's `acceptance/<id>.md` unit file, just nested as
  a subsection of one file instead of living as a separate file.

  **`kind: compiled` dispatch MUST use `criterion-compiler`'s
  `compile_criterion` primitive (`R-COMPILE-012`), never its
  directory-scanning `compile`** — a capability scenario is never
  stored under any one component's `acceptance/` directory, so
  `compile`'s own component-scoped path resolution can never find it.
  Pass `surface=None` — a capability scenario is black-box against the
  whole assembled system, not bound to one component's own `interface/`
  contract, so there is no single surface to resolve against; a step
  that still references a function/type with none supplied is a
  located compile error, same as always, never silently skipped.

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

  The exact `judge`/`test_author` callable contract (bundle shape,
  caching posture) is `R-SCENARIO-003`'s own job, not restated here.
