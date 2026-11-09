# `CacheKey`

```json
{
  "spec_bundle_hash": "sha256:...",
  "gate_inputs_hash": "sha256:...",
  "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
  "model_pin": "claude-sonnet-5"
}
```

`gate_version` is `<gate_type>@<version>`, the gate type being one of
`CachedResult.md`'s and the part before `@`. A `CachedResult` put under a
key MUST have that same `gate_type`, or `put` raises
`SchemaValidationError` (`R-CACHE-007`).
