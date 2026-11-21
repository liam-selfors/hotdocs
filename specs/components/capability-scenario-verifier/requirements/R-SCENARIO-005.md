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

  It then runs `<interpreter> -m pytest -q -p no:cacheprovider <path>`
  with `repo_root` as the working directory, `PYTHONPATH` set to the
  code directory (`R-SCENARIO-002`) of every component in the
  capability's realizing set joined by `os.pathsep`, and a 120-second
  timeout. Exit code `0` is a `pass`. Any other exit code, a timeout, or
  a failure to start is a `fail`.

  `<interpreter>` is what the `python` adapter's `provision(repo_root)`
  reports (`D344`), the adapter loaded by path as
  `specs/architecture/asset-kinds.md`'s Lookup gives and called once per
  `run_capability_scenarios` call, before its first test runs. With no
  adapter, or `ok` false, no test runs and each scenario that would run
  one is a `fail`.
