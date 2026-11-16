# R-PROBE-006

**R-PROBE-006** — `probe` MUST return its findings ordered by check, in
  the order `R-PROBE-001` to `R-PROBE-005` define them, and within a
  check by line, then by message; `ok` is `true` exactly when none has
  severity `error`. Every file it writes is under one temporary directory
  that it removes before returning, whatever the outcome.
