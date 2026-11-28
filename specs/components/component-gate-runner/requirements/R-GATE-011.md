# R-GATE-011

**R-GATE-011** — When `check_provenance` misses with `reason` exactly
  `"environment differs"` (`D345`), `"dependency code differs"`
  (`D379`), `"hash formula differs"` or `"gates differ"` (`D394`), MUST
  first re-verify the committed
  code without regenerating it: `verify` with `make_closures`' judge and
  test author, as for a sealed component, then both scans
  (`interface/library.md`). When the report's
  `overall` is `"pass"` and `license_scan.blocked` is not `true`, it MUST write provenance once from
  the committed manifest and that report and return `reverified` true,
  calling nothing else: no generation, no attempt record. Any other
  outcome proceeds exactly as a miss (`R-GATE-002`), the re-verification
  discarded; the secret scan is not consulted (`D371`).
