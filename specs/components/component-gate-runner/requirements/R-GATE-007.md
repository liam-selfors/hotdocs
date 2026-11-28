# R-GATE-007

**R-GATE-007** — A component is sealed exactly when `provenance-checker`'s
  `current_sealed_key` returns a key for it (`D170`); this component
  reads `component.md` itself only for `main`'s `--reauthor` check
  (`R-GATE-012`). For a sealed component it MUST skip
  `provenance-checker`'s `check_provenance`, `spec-bundle-assembler`, and
  `generator` entirely, and call `verifier-orchestrator` to re-run its
  characterization tests against the code at `source_path`, then both
  scans (`R-GATE-005`).

  It MUST then call `provenance-writer`'s `write_sealed_provenance`
  exactly once, after verification and both scans, whatever the
  verification outcome. The
  key is read once, before verification, and its values are what is
  written. No attempt record and no `.provenance.json` is written for a
  sealed component. The result's `blocked` follows `R-GATE-004`'s
  `"verification_failed"` rule.
