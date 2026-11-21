# R-GEN-005

**R-GEN-005** — Before calling any model, generation MUST check
  `cache-manager` using the key `(spec_bundle_hash, gate_inputs_hash,
  gate_version, model_pin)` that `interface/library.md` defines; on a
  cache hit, the cached result MUST be returned and no model call MUST
  occur. `gate_inputs_hash` incorporates `retry_feedback`, so a blind
  call and an informed one never share an entry.
