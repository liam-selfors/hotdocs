# R-LICENSE-011

**R-LICENSE-011** — A corpus the operator configured but the scanner
  cannot use MUST fail closed, never degrade silently to
  not-evaluated. If `VAR-LICENSE-CORPUS-PATH` is set and the file is
  missing or cannot be read, `reason` is `"corpus-unreadable"`; if it
  is read but breaks a rule in `interface/data/ReferenceCorpus.md`,
  `reason` is `"corpus-invalid"`. In both cases `evaluated` is `false`
  and `blocked` is `true`: a gate that was switched on and cannot run
  stops the merge. `notified` follows `R-LICENSE-003` unchanged.
