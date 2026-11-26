# R-SECRET-010

**R-SECRET-010** — `gate_version(repo_root)` MUST return exactly the
  `gate_version` that `scan(repo_root)` would report (`R-SECRET-006`).
  It MUST NOT scan any file, call `cache-manager`, or write anything
  (`D163`).
