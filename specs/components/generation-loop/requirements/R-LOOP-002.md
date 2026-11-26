# R-LOOP-002

**R-LOOP-002** — An attempt whose generation produced files MUST then call
  `check_surface`. A report whose `ok` is false is outcome
  `surface_failed`, `surface_ok` false, and no verification runs for that
  attempt. Otherwise `surface_ok` is true and `verify` runs; an `overall`
  of `pass` is outcome `passed`, anything else `verification_failed`, and
  `overall` is recorded.
