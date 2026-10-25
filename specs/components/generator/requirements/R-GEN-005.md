# R-GEN-005

**R-GEN-005** — Before calling any model, generation MUST check
  `cache-manager` using the key `(spec_bundle_hash, gate_inputs_hash,
  gate_version, model_pin)`; on a cache hit, the cached result MUST be
  returned and no model call MUST occur.

  `gate_inputs_hash` MUST incorporate `retry_feedback` (`R-GEN-012`,
  restored by `D33`) when present — a blind call and a call carrying
  `retry_feedback` are materially different inputs and MUST NOT be able
  to collide in the cache, even for the same `spec_bundle_hash`/
  `model_pin`. `retry_feedback` being absent and `retry_feedback` being
  present both still hash deterministically, so this only widens what
  counts as "the same inputs," it doesn't weaken determinism. (`D31`
  briefly simplified this key away along with automatic retry; restored
  once `D33` brought the parameter itself back.)
