# R-PACKET-008

**R-PACKET-008** — "Residual risk" — non-blocking findings still worth a
  human's attention (e.g. a component whose `mutation_score` is below
  `1.0` even though its `overall` result still reads `"pass"`) — MUST
  be its own section, distinct from pass/fail results. Sourced
  entirely from `provenance-tracker`'s own `verification_report`
  (`R-PACKET-011`) — never a metric, such as `spec-linter`'s own
  `component_doc_words`, that no field this component actually reads
  ever carries.
