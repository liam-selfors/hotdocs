# R-SECRET-006

**R-SECRET-006** — `gate_version` MUST be
  `secret_scanner@3.0.0+detect-secrets.<V>`, where `<V>` is the
  installed `detect-secrets` package's version, so upgrading the
  library invalidates every cached result (`D30`). The `3.0.0` MUST be raised in this requirement whenever the
  skipped-directory list, the plugin set, or `R-SECRET-012`'s rules
  change.
