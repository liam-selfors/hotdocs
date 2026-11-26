# R-VERIFY-019

**R-VERIFY-019** — Every failed `compiled` or `generated-test` criterion
  MUST carry `failure_origin`: `"test"` when `test-supply` supplied no
  sound test (`R-VERIFY-002`), or when its file is among
  `mutation-scorer`'s `faulty_tests`, its result then `fail` with
  `failure_detail.message` `test fails in the mutation sandbox` and its
  committed test discarded with `test-supply`'s `discard`
  (`specs/architecture/mutation-runs.md`, "Faulty tests");
  `"environment"` as `R-VERIFY-020` states; else `"implementation"`.
