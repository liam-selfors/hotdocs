# R-REVIEW-009

**R-REVIEW-009** — When `assemble_criterion` raises for a criterion,
  `check` MUST report one finding, `criterion_id` that criterion,
  `kind` `bundle_unavailable`, `token` `""` and `message`
  `<criterion_id>: its bundle cannot be built: <the exception's message>`
  (such as `unknown asset kind: css`, for a kind whose adapter does not
  exist yet), skip that criterion's other checks and its model call,
  leave its `writable` entry `null`, and go on with the next criterion,
  never raising. `main` returns `1` when any finding is
  `bundle_unavailable`, since that criterion could not be checked
  (`D389`).
