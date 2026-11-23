# R-PROBE-007

**R-PROBE-007** — The stub run MUST give every test the pytest fixture
  `asset_runner`, which `specs/architecture/asset-kinds.md` gives a
  test that uses an asset, by writing the asset plugin
  `hotdocs_probe_assets.py` with exactly the source `interface/library.md`
  gives beside the test file and loading it with
  `-p hotdocs_probe_assets` (`D343`). For a declared `path`,
  `asset_runner(path)` returns a callable that raises
  `HotdocsProbeStubReached` whatever it is passed, so a test that calls
  an asset reached the code under test; a test that only takes the
  fixture, or only calls `asset_runner(path)`, reaches nothing. For any
  other `path` it raises `HotdocsProbeUndeclaredAsset`, a `KeyError`
  (`D369`): a path is declared when it is in `assets`, or, with `assets`
  `None`, when it neither begins with `gen/` or `/` nor has a `..` part.

  A `testcase` whose `failure` or `error` `message` contains
  `HotdocsProbeUndeclaredAsset`, however its name is module-qualified,
  did not reach the code under test and gives exactly one `test_bug`
  finding, severity `error`, `line` null, `message`
  `<testcase name>: <that message>` unchanged. A test that reaches
  nothing and passes gives `R-PROBE-005`'s `vacuous` finding, severity
  `warn`, `<testcase name> passed without reaching the code under test`.
