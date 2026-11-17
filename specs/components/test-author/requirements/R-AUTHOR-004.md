# R-AUTHOR-004

**R-AUTHOR-004** — Before calling any model, MUST check `cache-manager`
  using a key derived from `(criterion content hash, gate_inputs_hash,
  gate_version, model)` — mirrors `generator`'s R-GEN-005, at criterion
  granularity instead of component granularity.

  **`gate_version`'s `<gate_type>@<semver>` prefix MUST be exactly
  `generated_test`**, a `gate_type` of `cache-manager`'s registry
  (`interface/data/CachedResult.md`), which names the kind of cached
  artifact, not the producing component (`D56`).
