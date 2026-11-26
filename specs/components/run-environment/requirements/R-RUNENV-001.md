# R-RUNENV-001

**R-RUNENV-001** — `prepare` MUST provision the asset kinds in order:
  the implicit `python` kind, then each declared kind in declaration
  order, calling each kind's `provision(repo_root)` once however many
  assets declare it. It stops at the first kind with no adapter or whose
  report has `ok` false: `ok` is false and `failure_message` is
  `unknown asset kind: <kind>` or that report's `reason`, and no later
  kind or driver is provisioned. Otherwise `interpreter` is the `python`
  report's `interpreter`.
