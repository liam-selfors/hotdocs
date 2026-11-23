# R-PROBE-005

**R-PROBE-005** — When no earlier check found an `error`, `probe` MUST
  run the test once against the stub module, under the interpreter
  `R-PROBE-008` gives, exactly as
  `interface/library.md` gives, and classify each `testcase` of the
  report:

  - a `failure` or `error` child whose `message` contains
    `HotdocsProbeUndeclaredAsset`: `R-PROBE-007`'s `test_bug` finding;
  - any other `failure` or `error` child whose `message` contains
    `HotdocsProbeStubReached` reached the code under test (an `error`
    one in a fixture): no finding;
  - an `error` child whose `message` is exactly
    `failed on setup with "AssertionError"`, after a `testcase` whose
    setup reached the code under test, reached nothing: pytest cannot set
    up later tests once that `BaseException` ends a setup (`D353`); no
    finding;
  - a `failure` whose `message` begins with `NameError`,
    `UnboundLocalError`, `ImportError` or `ModuleNotFoundError`, or any
    other `error` child, is a `test_bug` finding whose message is
    `<testcase name>: <message>`;
  - a `testcase` with no `failure`, `error` or `skipped` child passed
    without reaching the code under test: a `vacuous` finding, severity
    `warn`, message
    `<testcase name> passed without reaching the code under test`;
  - any other failure reached nothing this component can judge: no
    finding.

  A `testcase` whose `error` child's `message` is `collection failure`
  is pytest's record of a file it could not collect, not a test: it is
  never counted or classified as one. Such a record, a report with no
  `testcase` element, or a pytest exit code of `2`, `3` or `4` gives
  one `collection_error` finding, and only that, with pytest's last
  output line. A run still going after `timeout` seconds is killed and
  gives one `probe_timeout` finding. `tests_run` counts the `testcase`
  elements and `tests_reached` those that reached the code under test.
