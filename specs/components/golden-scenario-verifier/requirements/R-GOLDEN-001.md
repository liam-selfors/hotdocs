# R-GOLDEN-001

**R-GOLDEN-001** — Given a blast-radius component-id set, MUST determine
  every product capability whose `realizes`-set intersects it
  (`R-GOLDEN-002`) and run each one's golden scenarios against the real,
  fully assembled `gen/` output — not a prediction, the actual
  regenerated system. Each golden scenario MUST be dispatched by its
  declared `kind` using exactly the same mechanisms already wired for
  `verifier-orchestrator` (`criterion-compiler` for `compiled`,
  `test_author` for `generated-test`, `judge` for `llm-judge`) — no new
  dispatch machinery. The result MUST be keyed by `P-id`
  (`GoldenScenarioReport`), a distinct namespace from any single
  component's own verification result — this is a cross-component
  finding, never attributable to one component, and `merge-orchestrator`
  (`R-MERGE-011`) relies on that distinction to report it separately.
