# R-GATE-007

**R-GATE-007** — A component is sealed exactly when `provenance-checker`'s
  `current_sealed_key` returns a key for it (`D170`); this component
  never reads `component.md` itself. For a sealed component it MUST skip
  `provenance-checker`'s `check_provenance`, `spec-bundle-assembler`, and
  `generator` entirely, and call `verifier-orchestrator` to re-run its
  characterization tests against the code at `source_path`, then both
  scans (`R-GATE-005`). There is nothing to generate for a sealed
  component; re-running its tests unconditionally is what catches a hand
  edit at `source_path` that a spec-only hash would miss.

  It MUST then call `provenance-writer`'s `write_sealed_provenance`
  exactly once, after verification and both scans, whatever the
  verification outcome: a passing result records a current, passing
  manifest that makes the component ready, and a failing one records a
  failing manifest, so the owner and the failure are both on file. The
  key is read once, before verification, and its values are what is
  written. No attempt record and no `.provenance.json` is written for a
  sealed component. The result's `blocked` follows `R-GATE-004`'s
  `"verification_failed"` rule. `generator`'s `R-GEN-009` is the
  independent second layer of sealed-component write protection.
