# `CapabilityProvenanceCheckResult`

```json
{
  "hit": true,
  "capability_scenario_report": { "P-ZERO-EDIT": { "overall": "pass", "scenarios": [] } }
}
```

`capability_scenario_report` is a `CapabilityScenarioReport` holding
just the one `P-id`. `check_capability_provenance` sets it, copied from
the committed record, exactly when `hit` is `true`, and `null`
otherwise. `run_capability_gates` returns a hit unchanged; after a
fresh run it returns `hit` `false` with the fresh report, since nothing
was reused (`R-SCENARIO-004`). The shape mirrors `provenance-checker`'s
`ProvenanceCheckResult` so `provenance-tracker` reads both the same way.

## The committed record

`verification/capabilities/<capability_id>/.provenance.json`
(`R-SCENARIO-006`):

```json
{
  "capability_id": "P-ZERO-EDIT",
  "gate_version": "capability_scenario_verifier@2.1.0",
  "content_hash": "sha256:...",
  "realizing_components": ["comp-cache-manager"],
  "capability_scenario_report": { "P-ZERO-EDIT": { "overall": "pass", "scenarios": [] } },
  "model": "claude-sonnet-5",
  "seed": 0
}
```
