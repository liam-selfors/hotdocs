# R-MERGE-011

**R-MERGE-011** — The overall merge MUST be blocked if any impacted
  component's `ComponentPipelineResult` shows a failed one
  generation/verification attempt (`component-gate-runner`'s
  `R-GATE-004`), or a sealed component's characterization-test
  verification (`R-GATE-007`) failed, or either scanner reported a
  blocking flag — `LicenseScanResult.blocked` or
  `SecretScanResult.flagged` (not the same field name, `D66`) — or
  capability-scenario verification (R-MERGE-014) failed — and MUST
  proceed otherwise.

  The sealed-component case is listed explicitly, not folded into
  `R-GATE-004`: a sealed component never generates anything to fail
  (`R-GATE-007` skips `generator` entirely), so its failure mode is "the
  existing, hand-maintained code no longer satisfies its own
  characterization tests" — a different fact than "the one generation
  attempt failed" — with no other block condition that would otherwise
  catch it. Omitting it here would have been a real, silent gap.
