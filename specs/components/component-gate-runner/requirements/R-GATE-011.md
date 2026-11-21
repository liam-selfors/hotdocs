# R-GATE-011

**R-GATE-011** — When `check_provenance` misses with `reason` exactly
  `"environment differs"` (`D345`), MUST first re-verify the committed
  code without regenerating it: `verify` with `make_closures`' judge and
  test author, as for a sealed component, then both scans, as
  `interface/library.md` states. When the report's
  `overall` is `"pass"`, `license_scan.blocked` is not `true` and
  `secret_scan.flagged` is not `true`, it MUST write provenance once from
  the committed manifest and that report and return `reverified` true,
  calling nothing else: no generation, no attempt record. Any other
  outcome proceeds exactly as a miss (`R-GATE-002`), the re-verification
  discarded.
