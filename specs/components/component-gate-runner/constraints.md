# Component Gate Runner — Non-Functional Constraints

- **Determinism of sequencing, not of everything sequenced.** Given the
  same mocked dependency outputs, its call order and blocking decision
  MUST be reproducible.
- **No gate skipped silently.** A provenance hit (`R-GATE-001`) skips
  real work, but MUST be visible in `ComponentPipelineResult`.
- **Own wiring.** Closures come from its own `model`/`seed`/`llm_backend`
  (`R-GATE-002`, `D86`), never from a caller.
