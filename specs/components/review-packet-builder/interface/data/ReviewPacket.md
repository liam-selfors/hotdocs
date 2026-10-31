# `ReviewPacket`

```json
{
  "spec_diff": "<unified diff text>",
  "changed_requirements": ["R-FOO-001"],
  "regenerated_components": ["comp-foo"],
  "verification_results": { "comp-foo": { "...": "a VerificationReport" } },
  "compliance_flags": {
    "license_scan": [
      { "component_id": "comp-foo", "result": { "blocked": true, "...": "a LicenseScanResult" } }
    ],
    "secret_scan": []
  },
  "provenance_hit_status": { "comp-foo": false },
  "capability_scenarios": { "P-ZERO-EDIT": { "...": "a CapabilityScenarioReport" } },
  "exemption_changes": { "sealed": ["comp-foo"], "pinned_overrides": [] },
  "residual_risk": [
    { "component_id": "comp-foo", "message": "mutation_score 0.92 < 1.0 despite overall=pass" }
  ]
}
```

Each `residual_risk` entry is an object with `component_id` (the
affected component) and `message` (a human-readable description of
the non-blocking finding, per `R-PACKET-008`) — never a bare string.

Each `compliance_flags.license_scan`/`secret_scan` entry is a
`{"component_id", "result"}` pair, included only for a component
whose own `license_scan.blocked` / `secret_scan.flagged` is `true`
(`R-PACKET-005`) — the array is `[]`, not omitted, when none are.

`exemption_changes.sealed`/`pinned_overrides` entries are bare
component ids (`"comp-foo"`, matching `regenerated_components`'s own
shape) — never the `specs/components/<slug>/component.md` or
`gen/<slug>/.overrides.json` file path the change was detected in.

`capability_scenarios` (`R-PACKET-011`, `D90`) is every product
capability whose `realizes`-set intersects `regenerated_components`,
keyed by `P-id` — read from `provenance-tracker`'s `VerifyReport.capabilities`,
never a live `capability-scenario-verifier` call. A distinct section
from `verification_results`, never conflated with it — a cross-component
finding and a single-component one point a reviewer to different
places to look.
