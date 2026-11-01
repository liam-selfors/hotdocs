# R-SECRET-009

**R-SECRET-009** — Mirroring `license-scanner`'s R-LICENSE-007: when a
  scan flags, the files are then cleaned, and the scan runs again, the
  flagged `SecretScanResult` MUST remain recorded in `cache-manager`
  under its own key — the clean result is written under a different
  key, never overwriting it.
