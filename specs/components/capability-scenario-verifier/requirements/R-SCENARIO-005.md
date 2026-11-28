# R-SCENARIO-005

**R-SCENARIO-005** — A `compiled` or `generated-test` scenario MUST be
  decided by running its test, never by a test merely having been
  produced.

  A `compiled` scenario's test is the `source` that `compile_criterion`
  returns; a `status` of `"error"` is a `fail` with nothing written or
  run. A `generated-test` scenario's test is the `file` (`path`,
  `content`) its `test_author` returns; a `model_call_error`, or no
  file, is a `fail`.

  The runner writes the test itself, overwriting any earlier copy. A
  `generated-test` file goes to its returned `path`, which MUST be
  relative, under `verification/`, with no `..` segment, else the
  scenario is a `fail` and nothing is written. A `compiled` test goes to
  `verification/capabilities/<P-id>/compiled/test_<scenario id
  lowercased, `-` as `_`>.py`.

  It then runs `<interpreter> -m pytest -q -p no:cacheprovider
  <pytest_args()...> <path>` with `repo_root` as the working directory,
  `PYTHONPATH` the code directory (`R-SCENARIO-002`) of every component
  in the capability's realizing set, then `plugin_dir`, joined by
  `os.pathsep`, the environment's `env_for(repo_root)` variables, and a
  120-second timeout. Exit code `0` is a `pass`. Any other exit code, a timeout, or
  a failure to start is a `fail`.

  The environment is `run-environment`'s
  `prepare_capability(capability_id, repo_root)`, called once per
  capability before its first test runs and closed after its last
  (`D383`), giving the `python` kind's interpreter and the capability's
  declared test drivers (`D373`). With `ok` false, no test runs and each
  scenario that would run one is a `fail`.
