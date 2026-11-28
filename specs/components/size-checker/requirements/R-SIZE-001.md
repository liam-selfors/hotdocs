# R-SIZE-001

**R-SIZE-001** — The linter MUST compute the nine size-cap dimensions of
  `specs/architecture/size-caps.md` per component (`generated_code_loc`,
  `generator_words`, `criterion_words_max`, `requirement_count`,
  `interface_surface`, `fan_out`, `fan_in`, `guarantee_count`,
  `acceptance_count`) and report each at `warn` or `fail` severity per
  its thresholds (`D380`). `generator_words` and `criterion_words_max`
  MUST be queried from the `bundle_size` view (`R-GQE-009`) on
  `load_corpus`'s `graph` connection, `SELECT component_id,
  generator_words, criterion_words_max FROM bundle_size`, `component_id`
  being the bare slug, never recomputed independently, so one definition serves every reader.
