# `ReviewPacket`

```json
{
  "spec_diff": "<unified diff text>",
  "changed_requirements": ["R-FOO-001"],
  "regenerated_components": ["comp-foo"],
  "verification_results": { "comp-foo": { "...": "a VerificationReport" } },
  "compliance_flags": { "license_scan": [], "secret_scan": [] },
  "provenance_hit_status": { "comp-foo": false },
  "capability_scenarios": { "P-ZERO-EDIT": { "...": "a CapabilityScenarioReport" } },
  "exemption_changes": { "sealed": [], "pinned_overrides": [] },
  "residual_risk": []
}
```

`capability_scenarios` (`R-PACKET-011`, `D90`) is every product
capability whose `realizes`-set intersects `regenerated_components`,
keyed by `P-id` — read from `provenance-tracker`'s `VerifyReport.capabilities`,
never a live `capability-scenario-verifier` call. A distinct section
from `verification_results`, never conflated with it — a cross-component
finding and a single-component one point a reviewer to different
places to look.
