# R-TRACK-016

**R-TRACK-016** — `check_readiness` MUST judge secrets by one fresh
  `secret-scanner` `scan(repo_root)` of the repository, never by any
  component's stored `secret_scan`, exactly as
  `specs/architecture/repository-secret-scan.md` states: called once
  when the scope holds a component and no `precondition_error`, its
  result reported as `VerifyReport.secret_scan`, and a flagged result
  or a failed scan making the report not ready with one entry that names
  `secret_scan` (`D371`).
