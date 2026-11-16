# R-COMPILE-004

**R-COMPILE-004** — Compiled test output for a criterion MUST carry that
  criterion's `Covers:` id as metadata in the emitted code, as the
  comment line `# Covers: <id>`, so a failing test
  traces back to its `R-id`/`P-id` without re-parsing `acceptance/`.
