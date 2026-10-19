# R-PROV-002

**R-PROV-002** — `spec_bundle_hash`, `model_pin`, `prompt_version`,
  `sample_index`, and `retry_feedback` MUST be populated from `generator`'s
  `GenerationResult` — `retry_feedback` copied through exactly as
  `GenerationResult` recorded it (R-GEN-010), including `null` when the
  winning sample was a sequence's first attempt.
