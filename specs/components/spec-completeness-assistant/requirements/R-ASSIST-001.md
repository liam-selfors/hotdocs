# R-ASSIST-001

**R-ASSIST-001** — MUST run `spec-linter` over the whole corpus first and
  put every finding in `lint_findings`. If any finding has `severity`
  `"fail"` and a `file` inside a changed component's directory
  (`specs/components/<slug>/`, as `interface/library.md` defines changed
  components), `assist` MUST return immediately with `halted` true and
  nothing else run: `predicted_blast_radius` `[]`, `criterion_reviews`
  `{}`, `completeness_score`/`completeness_rationale` `null`,
  `redundancy_flags` `[]`, and no further dependency call of any kind. A
  `"fail"` finding anywhere else is reported but does not halt, and
  `halted` is false.

  Stopping, not merely ordering, is load-bearing (`D155`): judging a
  change whose own files fail lint spends money on a result the
  developer must discard. Halting on a failure elsewhere in the corpus
  made `assist` unusable on any corpus with one unrelated problem
  (`D301`).
