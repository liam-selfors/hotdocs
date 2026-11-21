# R-PROBE-007

**R-PROBE-007** — The stub run MUST give every test the pytest fixture
  `asset_runner`, which `specs/architecture/asset-kinds.md` gives a
  test that uses an asset, by writing the asset plugin
  `hotdocs_probe_assets.py` with exactly the source `interface/library.md`
  gives beside the test file and loading it with
  `-p hotdocs_probe_assets` (`D343`). `asset_runner(path)` returns, for
  any `path`, a callable that raises `HotdocsProbeStubReached` whatever
  it is passed, so a test that calls an asset reached the code under
  test and is classified as `R-PROBE-005` says; a test that only takes
  the fixture, or only calls `asset_runner(path)`, reaches nothing.
