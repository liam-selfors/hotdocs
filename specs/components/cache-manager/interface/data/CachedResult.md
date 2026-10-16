# `CachedResult`

```json
{
  "gate_type": "license_scanner",
  "payload": { "...": "gate-specific result shape" },
  "stored_at": "2026-10-02T00:00:00Z"
}
```

`gate_type` MUST match one of the known gate types (`compiler`,
`generated_test`, `llm_judge`, `cross_model_check`, `license_scanner`,
`secret_scanner`) and `payload`'s shape MUST match that type's expected
schema — enforced by `put` (R-CACHE-007), not left to the caller's
discipline.
