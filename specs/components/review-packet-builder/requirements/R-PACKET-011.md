# R-PACKET-011

**R-PACKET-011** — Every field sourced from `verifier-orchestrator`,
  `license-scanner`, or `secret-scanner` (R-PACKET-004, 005) MUST be
  read via the `component_provenance` view named in
  `specs/architecture/graph-query-engine.md`'s "Query surface" section
  — directly from `provenance-writer`'s already-written manifests,
  which already embed `verification_report`, `license_scan`,
  `secret_scan`, and `provenance_hit` (`SPEC_GUIDELINES.md` §7) — not a
  live call into any of those components. `provenance_hit` itself
  (R-PACKET-006) is this same manifest field, never a live
  `provenance-checker` call either.

  This is an implementation requirement, not a behavioral one —
  R-PACKET-001 through 010 are unaffected. It is also why this
  component's `depends_on` no longer lists those components (D26):
  they were never needed as live dependencies, only their
  already-written output was, and that output arrives through
  `provenance-writer`, which this component already depended on.
