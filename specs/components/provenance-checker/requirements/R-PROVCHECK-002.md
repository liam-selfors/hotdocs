# R-PROVCHECK-002

**R-PROVCHECK-002** — On a `spec_bundle_hash` match, MUST report a hit
  — returning the matching manifest's `verification_report`,
  `license_scan`, and `secret_scan` verbatim, never recomputed or
  summarized — **unless** the embedded `verification_report.criteria[]`
  contains an `llm-judge`-kind entry **and** `VAR-TRUST-JUDGE-PROVENANCE`
  resolves to `false`, in which case this is R-PROVCHECK-003's job
  instead. A hash match for a component whose acceptance set has no
  `llm-judge`-kind criterion at all is always honored as a hit,
  unconditionally — the variable only ever governs the one criterion
  kind that cannot be cheaply re-derived.
