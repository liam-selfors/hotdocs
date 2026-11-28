# R-RUNENV-004

**R-RUNENV-004** — When provisioning succeeds, `prepare` MUST write
  `plugin_dir`, a fresh temporary directory holding only
  `hotdocs_run_plugins.py`, the plugin
  `specs/architecture/run-environment.md` defines, and `env_for` MUST
  return exactly that document's `HOTDOCS_ASSETS` and `HOTDOCS_DRIVERS`
  for the given code directory. A pytest run of a test file with
  `pytest_args()`, `plugin_dir` last on `PYTHONPATH` and `env_for`'s
  variables gets the `asset_runner` fixture and each declared driver's
  fixture.
