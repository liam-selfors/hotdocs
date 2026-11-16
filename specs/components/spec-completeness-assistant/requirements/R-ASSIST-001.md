# R-ASSIST-001

**R-ASSIST-001** — MUST run `spec-linter` over the whole corpus first and
  put every finding, unchanged, in `lint_findings`. If any finding has
  `severity` `"fail"` and lies inside a changed component (as
  `interface/library.md` defines both), `assist` MUST return at once with
  `halted` true, `predicted_blast_radius` `[]`, `criterion_reviews` `{}`,
  `completeness_score`/`completeness_rationale` `null`,
  `redundancy_flags` `[]`, and no dependency call after `lint`; the
  `glossary_judge` call made before `lint` with a `model` still happens,
  and `degraded` is false exactly when a `model` was given. A `"fail"`
  finding anywhere else is reported but does not halt, and `halted` is
  false.

  Judging a change whose own files fail lint wastes a model call
  (`D155`); halting on unrelated failures made `assist` unusable
  (`D301`).
