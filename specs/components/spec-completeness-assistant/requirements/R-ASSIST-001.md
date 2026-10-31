# R-ASSIST-001

**R-ASSIST-001** — MUST run `spec-linter` against the draft spec change
  first. If any finding has `severity` `"fail"`, `assist` MUST return
  immediately with `lint_findings` populated and nothing else run:
  `predicted_blast_radius` `[]`, `hint_previews` `{}`,
  `completeness_score`/`completeness_rationale` `null`,
  `redundancy_flags` `[]`, and no model call of any kind, including
  `generator`'s hint preview. Same "cheap, deterministic gate first"
  ordering `hotdocs generate`'s own workflow uses, on the feature-branch
  side.

  Stopping, not merely ordering, is load-bearing (`D155`): `assist`
  returns one report, so "surfaced before" is only observable as a
  stop, and running a paid judgment or preview against a spec that
  already hard-fails lint spends money on a result the developer must
  discard anyway. `degraded` still reports only whether a model was
  configured (`R-ASSIST-007`); a caller tells a lint halt apart by the
  `"fail"`-severity entry in `lint_findings`.
