# Component Gate Runner — Non-Functional Constraints

- **Determinism of sequencing, not of everything sequenced.** Given the
  same mocked dependency outputs, this component's own call order and
  blocking decision for one component MUST be reproducible — the same
  posture `verifier-orchestrator` and `merge-orchestrator` already
  follow.
- **No gate skipped silently.** A provenance hit (`R-GATE-001`) skips
  real work, but MUST be visible in `ComponentPipelineResult`.
- **No wiring duplication.** `test_author`/`judge` arrive already wired
  (`R-GATE-002`) — this component MUST NOT construct its own closures
  or capture a model identifier itself; that stays the one wiring site
  in `merge-orchestrator` (`D76`).
