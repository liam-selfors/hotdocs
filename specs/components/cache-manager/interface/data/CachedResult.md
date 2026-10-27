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
discipline. `generator` was a real, pre-existing gap: this component's
own `Purpose` names `generator` as a consumer, but the original
gate-type list omitted it — found only once a real `generator` was
actually wired to call `put`/`get` for its own `GenerationResult`
payloads.

**Each gate type's exact required top-level payload keys** (`D40` —
  this table, not just R-CACHE-007's prose assertion that validation
  happens, MUST live here: a dependent only ever sees a dependency's
  `interface/` content, never its `requirements/` — R-ASSEMBLE-002 —
  so a `requirements/`-only copy of this table is invisible to a cold-
  mode caller assembling a real `put` call against this contract):

| `gate_type` | Required top-level payload keys |
| --- | --- |
| `generator` | `component_id`, `model`, `prompt_version`, `files` |
| `compiler` | `outputs`, `gate_version`, `summary` |
| `generated_test` | `component_id`, `criterion_id`, `model`, `file` |
| `llm_judge` | `result`, `rationale` |
| `license_scanner` | `component_id`, `gate_version`, `similarity_score`, `blocked`, `matches` |
| `secret_scanner` | `scope`, `gate_version`, `flagged`, `matches` |

A deliberately shallow key-presence check, not a full JSON-schema
validator — extra keys are permitted; only a missing required key
rejects a `put`.
