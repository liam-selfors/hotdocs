# R-LICENSE-002

**R-LICENSE-002** — Every evaluated scan MUST return a complete
  `LicenseScanResult`, clean or flagged: a clean one has `blocked`
  `false`, its `similarity_score`, and `matches` `[]`, never a null or
  empty result. Recording it is the caller's job: `provenance-writer`
  writes it into the manifest's `license_scan` field (`D378`).
