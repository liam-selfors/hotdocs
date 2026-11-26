# R-LICENSE-004

**R-LICENSE-004** — Before scanning, the scanner MUST check
  `cache-manager` using key `(spec_bundle_hash, gate_inputs_hash,
  gate_version, model_pin)`; on a
  cache hit, the cached result MUST be reused and no rescan MUST occur.
