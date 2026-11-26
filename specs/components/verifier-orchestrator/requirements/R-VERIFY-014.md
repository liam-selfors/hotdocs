# R-VERIFY-014

**R-VERIFY-014** — Every criterion's test run MUST have a wall-clock
  timeout of `DEFAULT_TEST_TIMEOUT` seconds, read at each run, killing
  the whole process tree as `specs/architecture/run-environment.md`'s
  "Timeouts" states; a timeout fails that criterion. Mutation runs'
  timeouts are `mutation-scorer`'s.
