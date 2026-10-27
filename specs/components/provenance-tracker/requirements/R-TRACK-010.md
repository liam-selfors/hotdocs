# R-TRACK-010

**R-TRACK-010** — `check_readiness` (`R-TRACK-009`) MUST additionally
  call `capability-scenario-verifier`'s `run_capability_gates`
  (`D89`/`D92`) for every product capability whose `realizes`-set is
  fully covered by the component scope just resolved — only after
  every one of that capability's realizing components' own
  `run_component_gates` call has concluded, so the scenarios run
  against each component's real, just-produced `gen/` content, never a
  stale copy from before this `hotdocs build` call started. Passes the
  same `model`/`seed`/`llm_backend` through unchanged, never
  re-deriving its hit/miss logic, only calling through to it the same
  way `R-TRACK-009` does for `component-gate-runner`.
  `VerifyReport.ready` MUST be `true` if and only if every component in
  scope came back passing **and** every intersecting capability did
  too — a single component or capability failing either makes `ready`
  false, with that item named in the report, same as `R-TRACK-009`'s
  per-component detail.
