# `CapabilityProvenanceCheckResult`

```json
{
  "hit": true,
  "capability_scenario_report": { "...": "a CapabilityScenarioReport, for just this one P-id" }
}
```

`capability_scenario_report` is populated whenever `hit` is `true` (a
prior run's result, copied verbatim from the committed record) or
whenever `run_capability_gates` just produced a fresh one — `null` only
for a `check_capability_provenance` call that found no record at all.
Mirrors `provenance-checker`'s `ProvenanceCheckResult` shape
deliberately — `provenance-tracker`'s `hotdocs verify` (`D88`) reads
both the same uniform way.

The committed record at
`verification/capabilities/<capability_id>/.provenance.json` carries
the same `capability_scenario_report` plus the realizing-components
content hash it was computed against (`R-SCENARIO-004`) — the part
`check_capability_provenance` compares against current state, never
exposed to a caller beyond the `hit`/miss verdict itself.
