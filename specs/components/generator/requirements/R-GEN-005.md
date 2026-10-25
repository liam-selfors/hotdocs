# R-GEN-005

**R-GEN-005** — Before calling any model, generation MUST check
  `cache-manager` using the key `(spec_bundle_hash, gate_version,
  model_pin)`; on a cache hit, the cached result MUST be returned and no
  model call MUST occur.

  Simplified by `D31`: this key no longer needs a separate
  `gate_inputs_hash` component incorporating `retry_feedback`/`seed` —
  with no retry loop left to vary either across calls, a cache-miss
  generation call now has nothing else that could make two calls for the
  same `spec_bundle_hash`/`model_pin` materially different from each
  other.
