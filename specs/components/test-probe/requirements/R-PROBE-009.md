# R-PROBE-009

**R-PROBE-009** — The stub run MUST give every test a fixture for each
  name in `drivers`, through the asset plugin exactly as
  `interface/library.md` gives it (`D373`): an object any of whose
  attributes, read, raises `HotdocsProbeStubReached`, so a test that uses
  a driver reached the code under test, and one that only takes the
  fixture reaches nothing. A fixture name not in `drivers` is unknown to
  pytest, an `error` at setup, and so a `test_bug` finding.
