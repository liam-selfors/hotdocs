# R-PACKET-011

**R-PACKET-011** — Every field sourced from `verifier-orchestrator`,
  `license-scanner`, `secret-scanner`, or `capability-scenario-verifier`
  (R-PACKET-004, 005, and the capability-scenario section this
  requirement adds) MUST be read via `provenance-tracker`'s own
  `check_readiness` (`D90`) — its `VerifyReport.components`/
  `capabilities` maps already carry `verification_report`,
  `license_scan`, `secret_scan`, and the real field named literally
  `hit` (never `provenance_hit` — that's only this *packet's own*
  output field name, `provenance_hit_status`, R-PACKET-006), and each
  intersecting capability's own `CapabilityScenarioReport` — never a
  live call into any of those components directly, nor a live
  `provenance-checker` call either.

