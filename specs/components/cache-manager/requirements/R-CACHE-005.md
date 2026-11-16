# R-CACHE-005

**R-CACHE-005** — `gate_version` MUST be part of the lookup key itself, not
  metadata checked after retrieval — a `get` for `gate_version: "2.0.0"` MUST
  NOT return an entry stored under `gate_version: "1.0.0"`, even if every
  other key component matches.
