# R-LICENSE-005

**R-LICENSE-005** — The reference corpus/signature database's own version
  MUST be part of `gate_version` (e.g. `license_scanner@3.1.0`) — reusing
  the original brainstorm's existing discipline that a gate's version is
  part of its own cache key, not restating it as a new mechanism. A
  signature-database
  update without a `gate_version` bump would let a stale cache hit mask a
  newly-added match; this requirement is what prevents that.
