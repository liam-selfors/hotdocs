# R-SIZE-001

**R-SIZE-001** — The linter MUST compute the eight `SPEC_GUIDELINES.md`
  §4 size-cap dimensions per component (`generated_code_loc`,
  `component_doc_words`, `requirement_count`, `interface_surface`,
  `fan_out`, `fan_in`, and — since `D17` — `guarantee_count`,
  `acceptance_count`) and report each at `warn` or `fail` severity per
  the published thresholds. `component_doc_words` MUST be queried from
  the `component_size` view (`specs/architecture/graph-query-engine.md`'s
  "Query surface" section, `D13`), never recomputed independently —
  `R-GRAPH-009` queries the same view, one definition, not two to drift.
