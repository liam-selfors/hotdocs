# R-SECRET-003

**R-SECRET-003** — Every scan MUST return a complete
  `SecretScanResult`, clean or flagged: a clean one has `flagged`
  `false` and `matches` `[]`, never a null or empty result. Recording it
  is the caller's job (`provenance-writer`, `D378`).
