# R-TRACK-010

**R-TRACK-010** — `check_readiness` (`R-TRACK-009`) MUST additionally
  call `capability-scenario-verifier`'s `run_capability_gates`
  (`D89`/`D92`, unreversed by `D93`) for every product capability whose
  `realizes`-set intersects the component scope just resolved, passing
  the same `model`/`seed`/`llm_backend` through unchanged, never
  re-deriving its hit/miss logic — unlike the component half
  (`R-TRACK-009`), this is check-then-run, not pure read, since
  capability-scenario verification never produces new source code, only
  exercises what already exists, so triggering it from `hotdocs verify`
  costs a developer nothing they wouldn't expect. If any such call would
  be a miss and `model` is `None`, MUST report a usage error rather than
  skip the capability or run it anyway.

  `VerifyReport.ready` MUST be `true` if and only if every component in
  scope is a provenance hit with a passing `verification_report` and no
  blocking scan result, **and** every intersecting capability comes back
  passing from `run_capability_gates` — a single component or capability
  failing either check makes `ready` false, with that item named in the
  report, same as `R-TRACK-009`'s per-component detail.
