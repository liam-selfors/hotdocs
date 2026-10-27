# R-MERGE-011

**R-MERGE-011** — The overall merge MUST be blocked if any impacted
  component's one generation/verification attempt failed (R-MERGE-006),
  or a sealed component's
  characterization-test verification (R-MERGE-015) failed, or either
  scanner reported a blocking flag — `LicenseScanResult.blocked` or
  `SecretScanResult.flagged` (not the same field name, `D82`) — or
  capability-scenario verification (R-MERGE-014) failed — and MUST
  proceed otherwise.

  The sealed-component case is listed explicitly, not folded into
  R-MERGE-006: a sealed component never generates anything to fail
  (R-MERGE-015 skips `generator` entirely), so its failure mode is "the
  existing, hand-maintained code no longer satisfies its own
  characterization tests" — a different fact than "the one generation
  attempt failed" — with no other block condition that would otherwise
  catch it. Omitting it here would have been a real, silent gap.
