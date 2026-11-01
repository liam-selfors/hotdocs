# R-GATE-007

**R-GATE-007** — For a component marked `sealed: true`, MUST skip
  `provenance-checker`, `spec-bundle-assembler`, and `generator`
  entirely, and invoke `verifier-orchestrator` directly against the
  component's existing code at its `source_path`, then both scans
  (`R-GATE-005`). There is nothing to generate for a sealed component;
  re-running its characterization tests unconditionally is what catches
  a hand edit at `source_path` that its spec-only hash would miss. No
  attempt record or provenance is written for it. The result's
  `blocked` follows `R-GATE-004`'s `"verification_failed"` rule.
  `generator`'s `R-GEN-009` is the independent second layer of
  sealed-component write protection.
