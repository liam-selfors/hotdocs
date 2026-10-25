# `GoldenScenarioReport`

```json
{
  "P-ZERO-EDIT": { "result": "pass", "scenarios": ["GS-ZERO-EDIT-001"] }
}
```

Keyed by `P-id` — one entry per product capability whose `realizes`-set
intersected the blast radius this run (`R-GOLDEN-001`/`R-GOLDEN-002`),
never one entry per component. `result` is `pass`/`fail`/`skipped`,
mirroring `VerificationReport`'s vocabulary. `scenarios` lists the
`GS-id`s actually run for that capability, for traceability back to
`specs/product/*.md`.

Passed through unchanged into `MergeResult.golden_scenarios`
(`merge-orchestrator`'s own data type) — this component returns the
value, it does not write anything to disk itself.
