# R-VERIFY-002

**R-VERIFY-002** — For every `generated-test`-kind criterion, this
  component MUST obtain its test from `test-supply`'s
  `supply(component_id, criterion_id, repo_root, test_author=...,
  interpreter=..., assets=..., drivers=...)`, with the run environment's
  `interpreter`, the declared asset paths and `driver_fixtures()`
  (`R-VERIFY-020`), execute the returned `path` against
  `gen/<component>/`, and record a pass/fail per criterion. A supplied
  test with `failure_origin` `"test"` is never run: the criterion is
  `fail` with that origin and `failure_detail.message` its
  `failure_message` (`D383`).
