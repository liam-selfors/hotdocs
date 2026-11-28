# R-LICENSE-010

**R-LICENSE-010** — Every `LicenseScanResult` MUST carry `evaluated`
  (boolean) and `reason`. `evaluated` is `true`, with `reason` `null`,
  only if a usable reference corpus (`interface/data/ReferenceCorpus.md`)
  with at least one entry was loaded and compared against. Otherwise
  `evaluated` is `false`, `similarity_score` and `block_threshold` are
  `null` (never `0.0`: no score was measured), `matches` is `[]`, and
  `reason` is exactly one of `"no-reference-corpus"` (the variable is
  unset or empty),
  `"corpus-unreadable"`, or `"corpus-invalid"` (`R-LICENSE-011`).
  `no-reference-corpus` MUST NOT block (`D193`). The webhook payload carries `evaluated` and `reason` too.
