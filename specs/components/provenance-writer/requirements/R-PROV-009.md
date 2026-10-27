# R-PROV-009

**R-PROV-009** — When `provenance_hit` is `true`, this component MUST
  still just write whatever `verification_report`/`license_scan`/
  `secret_scan` its `ProvenanceInputs` carries, unchanged — the same
  "collects, never invents" discipline as every other field. It MUST
  NOT look anything up itself. Sourcing those fields from the matching
  prior manifest, via `provenance-checker` (`D29`), is
  `merge-orchestrator`'s job before this component is ever called —
  this requirement previously described that lookup as this
  component's own, pointed at `cache-manager`, which never held a
  `VerificationReport` to look up in the first place.
