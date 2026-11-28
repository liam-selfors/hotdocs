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
  "capability_scenarios": { "P-ZERO-EDIT": { "P-ZERO-EDIT": { "overall": "pass", "scenarios": [] } } },
  "exemption_changes": { "sealed": ["comp-foo"], "pinned_overrides": [] },
  "screenshots": { "comp-foo": [".hotdocs/screenshots/foo/test_ac_foo_009/final-1.png"] },
  "residual_risk": [
    { "component_id": "comp-foo", "message": "mutation_score 0.92 < 1.0 despite overall=pass" }
  ]
}
```

Each `residual_risk` entry is an object with `component_id` (the
affected component) and `message` (a human-readable description of
the non-blocking finding, per `R-PACKET-008`) — never a bare string.

Each `compliance_flags.license_scan`/`secret_scan` entry is a
`{"component_id", "result"}` pair (`R-PACKET-005`). Each array is `[]`,
not omitted, when nothing is flagged.

`exemption_changes.sealed`/`pinned_overrides` entries are bare
component ids (`"comp-foo"`) — never the `specs/components/<slug>/component.md` or
`gen/<slug>/.overrides.json` file path the change was detected in.

`capability_scenarios` (`R-PACKET-011`, `D90`) is every product
capability whose `realizes`-set intersects `regenerated_components`,
keyed by `P-id`, each value that capability's `capability_scenario_report`
exactly as read (itself keyed by `P-id`, never unwrapped) — read from `provenance-tracker`'s `VerifyReport.capabilities`,
never a live `capability-scenario-verifier` call. A distinct section
from `verification_results`.

`screenshots` (`R-PACKET-014`) maps every regenerated component to
its verification's page screenshots, paths relative to `repo_root`;
an empty list, never an omitted key, when it has none.
