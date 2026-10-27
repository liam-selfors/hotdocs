# R-MERGE-003

**R-MERGE-003** — For each impacted, **non-sealed** component, MUST
  check `provenance-checker` (`D29`) before doing anything else; a hit
  MUST short-circuit straight to using the returned
  `verification_report`/`license_scan`/`secret_scan` as this
  component's results, skipping R-MERGE-004 through R-MERGE-008
  entirely — not running them and discarding the result. A sealed
  component is never checked against `provenance-checker` at all —
  R-MERGE-015 always runs for it directly, unconditionally. A miss
  falls through to R-MERGE-004 onward normally; this component never
  second-guesses `provenance-checker`'s verdict or re-derives it from
  `cache-manager`.
