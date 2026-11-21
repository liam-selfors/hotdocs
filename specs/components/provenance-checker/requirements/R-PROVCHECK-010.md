# R-PROVCHECK-010

**R-PROVCHECK-010** — A miss `R-PROVCHECK-009` reports as `assets
  differ` MUST instead have `reason` `environment differs` (`D345`)
  exactly when the manifest's `assets` is a list as long as the current
  value and each entry is an object with the current entry's keys whose `kind`, `path`,
  `definition_sha256` and `adapter_sha256` equal those of the current
  entry at its index: only `versions` or `lockfile_sha256` differ. Any
  other difference stays `assets differ`.
