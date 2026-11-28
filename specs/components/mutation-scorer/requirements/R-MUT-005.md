# R-MUT-005

**R-MUT-005** — Every run MUST be killed with its whole process tree when
  its timeout fires, as `specs/architecture/run-environment.md`'s
  "Timeouts" states, and `score` MUST NOT raise: an exception from an
  adapter is `mutation-runs.md`'s adapter failure, and any other
  becomes `mutation_error` `mutation run failed: <ExceptionType>:
  <message>`.
