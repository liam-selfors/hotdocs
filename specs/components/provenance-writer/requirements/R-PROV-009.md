# R-PROV-009

**R-PROV-009** — When `provenance_hit` is `true`, this component MUST
  still just write whatever `verification_report`/`license_scan`/
  `secret_scan` its `ProvenanceInputs` carries, unchanged. It MUST
  NOT look anything up itself. Sourcing those fields from the matching
  prior manifest, via `provenance-checker` (`D29`), is
  `component-gate-runner`'s job before this component is ever called
  (`D76`).
