# R-GATE-001

**R-GATE-001** — For a non-sealed component, MUST check
  `provenance-checker` (`D29`) before doing anything else; a hit MUST
  short-circuit straight to using the returned
  `verification_report`/`license_scan`/`secret_scan` as this
  component's results, skipping `R-GATE-002` through `R-GATE-005`
  entirely — not running them and discarding the result. A sealed
  component is never checked against `provenance-checker` at all —
  `R-GATE-007` always runs for it directly, unconditionally. A miss
  falls through to `R-GATE-002` onward normally; this component never
  second-guesses `provenance-checker`'s verdict or re-derives it from
  `cache-manager`.
