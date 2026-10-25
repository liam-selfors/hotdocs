# R-PROV-002

**R-PROV-002** — `spec_bundle_hash`, `model_pin`, `prompt_version`, and
  `retry_feedback` MUST be populated from `generator`'s
  `GenerationResult` — `retry_feedback` copied through exactly as
  recorded there (`R-GEN-012`, restored by `D33`), including `null`
  when the call was blind. No `sample_index` field — `D31` retired the
  best-of-k retry loop that gave it a meaning, and nothing since has
  reintroduced multiple samples per merge.
