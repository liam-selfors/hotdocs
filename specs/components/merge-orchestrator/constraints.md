# Merge Orchestrator — Non-Functional Constraints

- **Determinism of sequencing, not of everything sequenced.** Given the
  same mocked dependency outputs, this component's own call order and
  blocking decisions MUST be reproducible — the same posture
  `verifier-orchestrator` already follows.
- **Fail fast, cheapest gate first.** `spec-linter` (R-MERGE-001) MUST run
  before any component that costs a model call — getting this backward
  would burn generation cost on specs that were never going to lint clean.
- **No gate skipped silently.** A provenance hit (`component-gate-runner`'s
  `R-GATE-001`) skips real work, but MUST be visible in `MergeResult` and
  the review packet.
- **This component's own fan-out (9, down from 15 after `D76`) is
  accepted, not a defect** — see `D15` and `pipeline-decomposition.md`'s
  dedicated note.
- **Capability-scenario failure is its own result category, never
  conflated with a component's own verification result** (R-MERGE-014,
  `CapabilityScenarioReport`) — a cross-component finding and a
  single-component one point a developer to different fixes; collapsing
  them would undo the point of a separate gate.
