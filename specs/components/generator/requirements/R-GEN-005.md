# R-GEN-005

**R-GEN-005** — Before calling any model, generation MUST check
  `cache-manager` using the key `(spec_bundle_hash, gate_inputs_hash,
  gate_version, model_pin)`; on a cache hit, the cached result MUST be
  returned and no model call MUST occur.

  For this gate, `gate_inputs_hash` MUST incorporate `retry_feedback`
  (R-GEN-010) when present — hashing `seed` alone is not enough, because a
  retry attempt that supplies feedback and a blind retry that happens to
  reuse the same `seed` are materially different calls (one is informed by
  a prior failure, the other isn't) and MUST NOT be able to collide in the
  cache and silently return a result that was never actually produced with
  that feedback. `retry_feedback` being absent (a sequence's first attempt)
  and `retry_feedback` being present both still hash deterministically, so
  R-GEN-005's own cache-hit guarantee is unaffected — this only widens what
  counts as "the same inputs," it doesn't weaken determinism.
