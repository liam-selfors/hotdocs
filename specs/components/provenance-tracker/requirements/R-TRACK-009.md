# R-TRACK-009

**R-TRACK-009** — MUST expose `check_readiness(repo_root: Path, model:
  str, seed: int = 0, llm_backend=None, changed_ids: list[str] | None =
  None, retry_feedback: list[str] | None = None) -> VerifyReport`
  (`D88`/`D92`): given `changed_ids`, MUST call `impact-analyzer` to
  compute the blast radius, then call `component-gate-runner`'s
  `run_component_gates` for each component in it, passing
  `model`/`seed`/`llm_backend` through unchanged — this component never
  constructs or wires anything model-related itself — and
  `retry_feedback` only when `changed_ids` names exactly one component,
  never derived or applied to more than one.
  Given no `changed_ids` (or an empty list), MUST do the same for every
  component in `specs/components/` — the whole-corpus scope;
  `retry_feedback` MUST be rejected as a usage error in this scope,
  since it is only ever meaningful for a single named component.

  `run_component_gates` already checks its own provenance first and
  skips real work on a hit (`R-GATE-001`) — this requirement MUST NOT
  re-derive that hit/miss logic itself, only call through to it and use
  whatever `ComponentPipelineResult` comes back, whether fresh or a
  cache hit.

  **MUST sequence these calls in `depends_on` order within the scope**
  — a component's `run_component_gates` call MUST NOT start before
  every dependency in scope has finished its own (`R-ASSEMBLE-011`'s
  `dependency_usage` needs each one's `gen/` content current when a
  dependent's bundle is assembled). Components with no `depends_on`
  relationship between them MAY run in parallel. This moved here
  (`D92`) from being a developer's own manual-sequencing discipline
  across separate commands — now that one `hotdocs build` call can
  cover more than one component itself, it has to guarantee the
  ordering internally, the same obligation `merge-orchestrator`'s old
  `R-MERGE-023` once stated for the same reason.

  A component whose result shows a miss, a failed
  `verification_report`, or a blocking scan result is reported as not
  ready, with enough detail (which component, which check failed) for
  a human or `provenance-tracker-ui` to act on, never just a bare
  boolean.
