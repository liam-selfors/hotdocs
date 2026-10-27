# R-TRACK-010

**R-TRACK-010** — `check_readiness` (`R-TRACK-009`) MUST additionally
  check every product capability whose `realizes`-set intersects the
  component scope just resolved, calling `capability-scenario-verifier`'s
  own `check_capability_provenance` (`D89`) rather than re-deriving its
  hit/miss logic. `VerifyReport.ready` MUST be `true` if and only if
  every component in scope is a provenance hit with a passing
  `verification_report` and no blocking scan result, **and** every
  intersecting capability is a provenance hit with a passing
  `CapabilityScenarioReport` — a single component or capability failing
  either check makes `ready` false, with that item named in the
  report, same as `R-TRACK-009`'s per-component detail.
