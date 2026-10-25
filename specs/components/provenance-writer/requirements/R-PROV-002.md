# R-PROV-002

**R-PROV-002** — `spec_bundle_hash`, `model_pin`, and `prompt_version`
  MUST be populated from `generator`'s `GenerationResult`. No
  `sample_index`/`retry_feedback` fields — `D31` retired the best-of-k
  retry loop that gave either one a meaning, and `GenerationResult`
  itself no longer carries them.
