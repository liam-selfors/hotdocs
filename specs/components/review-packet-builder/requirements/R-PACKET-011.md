# R-PACKET-011

**R-PACKET-011** — Every field sourced from `verifier-orchestrator`,
  `license-scanner`, `secret-scanner`, or `cache-manager` (R-PACKET-004,
  005, 006, 008) MUST be read via the `component_provenance` view named
  in `specs/architecture/graph-query-engine.md`'s "Query surface" section
  — directly from `provenance-writer`'s already-written manifests, which
  already embed `verification_report`, `license_scan`, `secret_scan`, and
  `cache_hit` (`SPEC_GUIDELINES.md` §7) — not a live call into any of
  those four components. None of them write their own file for this
  component to read independently; `provenance-writer` already collected
  everything into one place.

  This is an implementation requirement, not a behavioral one —
  R-PACKET-001 through 010 are unaffected. It is also why this
  component's `depends_on` no longer lists those four components (D26):
  they were never needed as live dependencies, only their
  already-written output was, and that output arrives through
  `provenance-writer`, which this component already depended on.
