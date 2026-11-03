# R-SECRET-009

**R-SECRET-009** — When a scan flags, the files are then cleaned, and the
  scan runs again, the flagged `SecretScanResult` MUST remain recorded in
  `cache-manager` under its own key; the clean result is written under
  a different key and never overwrites it (as `R-LICENSE-007`).
