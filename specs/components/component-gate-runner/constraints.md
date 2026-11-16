# Component Gate Runner — Non-Functional Constraints

- **Determinism of sequencing, not of everything sequenced.** Given the
  same mocked dependency outputs, this component's own call order and
  blocking decision for one component MUST be reproducible — the same
  posture `verifier-orchestrator` already follows.
- **No gate skipped silently.** A provenance hit (`R-GATE-001`) skips
  real work, but MUST be visible in `ComponentPipelineResult`.
- **Own wiring, own closures.** `test_author`/`judge` are constructed
  by this component itself from its own `model`/`seed`/`llm_backend`
  parameters (`R-GATE-002`, `D86`) — not received already-wired from a
  caller, since nothing calls this component on a developer's behalf
  anymore.
