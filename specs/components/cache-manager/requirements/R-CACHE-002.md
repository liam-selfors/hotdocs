# R-CACHE-002

**R-CACHE-002** — The cache key MUST be exactly the 4-tuple
  `(spec_bundle_hash, artifact/gate-inputs hash, gate_version, model_pin)`
  (D13), computed identically regardless of which calling component invokes
  `get`/`put` — the key-formation logic is this component's responsibility,
  not each caller's, so every gate hashes consistently.
