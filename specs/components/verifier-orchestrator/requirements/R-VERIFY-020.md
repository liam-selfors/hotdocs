# R-VERIFY-020

**R-VERIFY-020** — For a component that is not sealed (`R-VERIFY-017`),
  before any criterion runs, `verify` MUST call
  `run-environment`'s `prepare(component_id, repo_root)` once (`D383`).
  When it reports `ok` false, every `generated-test` and `compiled`
  criterion is `fail` with `failure_origin` `"environment"` and
  `failure_detail.message` its `failure_message`, none is supplied or
  run, and `mutation_score` and `mutation_error` are null. Otherwise
  every criterion run is under its `interpreter`, with its
  `pytest_args()`, its `plugin_dir` last on `PYTHONPATH` and
  `env_for(<repo_root>/gen/<slug>)`, and `close()` is called before
  `verify` returns. The report's `assets` and `drivers` are its own.
