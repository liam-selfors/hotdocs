# `MergeResult`

```json
{
  "blocked": false,
  "components": {
    "comp-foo": { "...": "a ComponentPipelineResult" }
  },
  "capability_scenarios": {
    "P-ZERO-EDIT": {
      "overall": "pass",
      "scenarios": [{ "id": "CS-ZERO-EDIT-001", "kind": "generated-test", "result": "pass" }]
    }
  },
  "review_packet": { "...": "a ReviewPacket" },
  "block_reasons": [],
  "tracking_write_error": null
}
```

No `attempts`/`sample_index` fields — `D3` retired the best-of-k retry
loop that gave either one meaning beyond "always 1"/"always 0."
Each `components[id]` entry is a `component-gate-runner`
`ComponentPipelineResult` (`D76`), collected unchanged by this
component into `MergeResult.components`, keyed by `component_id` — see
that type's own spec for its field shape.
`capability_scenarios`
(R-MERGE-014) is `capability-scenario-verifier`'s
`CapabilityScenarioReport` return value, passed through unchanged —
keyed by `P-id`, covering every capability whose `realizes`-set
intersects this merge's blast radius — a distinct result category from
`components`, never merged into any single component's own entry (per
`constraints.md`'s "never conflated" rule). `tracking_write_error`
(R-MERGE-019, `D25`) is `{category, message}` or `null`, mirroring
`model_call_error`'s shape — set only if `merge-tracker` itself raised;
it never affects `blocked`/`block_reasons`, per `R-TRACK-005`.
