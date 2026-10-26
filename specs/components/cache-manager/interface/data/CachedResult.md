# `CachedResult`

```json
{
  "gate_type": "license_scanner",
  "payload": { "...": "gate-specific result shape" },
  "stored_at": "2026-10-02T00:00:00Z"
}
```

`gate_type` MUST match one of the known gate types (`generator`,
`compiler`, `generated_test`, `llm_judge`, `license_scanner`,
`secret_scanner`) and `payload`'s shape MUST match that type's expected
schema — enforced by `put` (R-CACHE-007), not left to the caller's
discipline. `generator` (added `D50`) was a real, pre-existing gap: this
component's own `Purpose` names `generator` as a consumer, but the
original gate-type list omitted it — found only once a real `generator`
was actually wired to call `put`/`get` for its own `GenerationResult`
payloads.
