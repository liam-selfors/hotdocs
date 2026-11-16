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

  **The review packet now includes a capability-scenario section** —
  found missing entirely from this component's own prior scope, even
  though the component this packet reports for always intended it
  (`merge-orchestrator`'s old `R-MERGE-010`, before `D87` removed that
  component, already assumed review packets carried this; nothing in
  this component's own spec ever added the requirement to actually do
  it). `provenance-tracker`'s uniform component/capability aggregation
  (`D88`/`D89`) is what makes this straightforward now — one read
  source instead of a second, bespoke one for capability results alone.

  This is an implementation requirement, not a behavioral one —
  R-PACKET-001 through 010 are unaffected beyond gaining the new
  capability-scenario section. It is also why this component's
  `depends_on` lists only `provenance-tracker` (`D90`): no other
  component's own output needs to be read directly, only
  `provenance-tracker`'s already-assembled aggregate.
