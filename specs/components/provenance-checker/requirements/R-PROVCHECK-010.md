# R-PROVCHECK-010

**R-PROVCHECK-010** — A miss `R-PROVCHECK-009` reports as `assets differ`
  or `drivers differ` MUST instead have `reason` `environment differs`
  (`D345`) exactly when, for each of `assets` and `drivers`, the
  manifest's list is as long as the current value and each entry is an
  object with the current entry's keys, equal to it in every key but
  `versions` and `lockfile_sha256`. Any other difference keeps its
  reason.
