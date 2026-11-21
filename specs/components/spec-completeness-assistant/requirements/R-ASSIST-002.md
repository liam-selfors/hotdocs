# R-ASSIST-002

**R-ASSIST-002** — MUST call `impact-analyzer`'s `compute_blast_radius`
  with `changed_ids` and `repo_root` exactly as received and set
  `predicted_blast_radius` to the `component_id` of each `impacted`
  entry, in order, one per entry — or `[]` when `precondition_error` is
  non-null. This is the "Predicted blast radius" metric
  (`notes/metrics.md`).
