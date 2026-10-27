# `CapabilityScenarioReport`

```json
{
  "P-ZERO-EDIT": {
    "overall": "pass",
    "scenarios": [
      { "id": "CS-ZERO-EDIT-001", "kind": "generated-test", "result": "pass" }
    ]
  }
}
```

A capability with more than one scenario, including one `llm-judge`-kind
scenario that failed:

```json
{
  "P-FOO": {
    "overall": "fail",
    "scenarios": [
      { "id": "CS-FOO-001", "kind": "compiled", "result": "pass" },
      { "id": "CS-FOO-002", "kind": "llm-judge", "result": "fail", "rationale": "..." }
    ]
  }
}
```

Keyed by `P-id` — one top-level entry per product capability whose
`realizes`-set intersected the blast radius this run
(`R-SCENARIO-001`/`002`), never one entry per component. `scenarios` is
one entry **per capability scenario** (`D23` — moved off the single
aggregate verdict `GoldenScenarioReport` used to have, the same
per-criterion granularity `VerificationReport.criteria[]` already has),
each carrying its own `id`, `kind`, and `result` (`pass`/`fail`/
`skipped`, mirroring `VerificationReport`'s vocabulary exactly).
`rationale` is present only on entries whose `kind` is `llm-judge` and
that actually dispatched — `SPEC_GUIDELINES.md` §5's existing,
corpus-wide rule ("An `llm-judge` criterion MUST emit structured
rationale alongside its verdict"), the same field `VerificationReport.
criteria[]` and `Finding` already carry for the same reason. `overall`
aggregates the capability's own `scenarios` the same way
`VerificationReport.overall` aggregates `criteria` (`R-VERIFY-005`): a
`skipped` `llm-judge` scenario alone doesn't fail `overall`, a genuine
`fail` does.

Passed through unchanged into `MergeResult.capability_scenarios`
(`merge-orchestrator`'s own data type) — this component returns the
value, it does not write anything to disk itself.
