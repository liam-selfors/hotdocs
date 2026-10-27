# R-SECRET-005

**R-SECRET-005** — Before scanning, the scanner MUST check
  `cache-manager` using key `(spec_bundle_hash, gate_inputs_hash,
  gate_version, model_pin)` — `cache-manager`'s own canonical field
  name (`interface/data/CacheKey.md`), not an informal alias; on a
  cache hit, the cached result MUST be reused.
