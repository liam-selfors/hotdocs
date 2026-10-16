# Merge Orchestrator — Non-Functional Constraints

- **Determinism of sequencing, not of everything sequenced.** Given the
  same mocked dependency outputs, this component's own call order and
  blocking decisions MUST be reproducible — the same conditional structure
  every other coordination component in this corpus (`verifier-orchestrator`,
  `cross-model-divergence-checker`) already follows.
- **Fail fast, cheapest gate first.** `spec-linter` (R-MERGE-001) MUST run
  before any component that costs a model call — this ordering is itself a
  constraint, not an implementation detail, since getting it backward would
  burn generation cost on specs that were never going to lint clean.
- **No gate skipped silently.** A cache hit (R-MERGE-003) and a
  toggle-disabled cross-model check (R-MERGE-007) both skip real work, but
  both MUST be visible in `MergeResult` and the review packet — never
  indistinguishable from "this gate ran and found nothing."
- **This component's own fan-out (12 dependencies) is accepted, not a
  defect** — see `specs/architecture/pipeline-decomposition.md`'s dedicated
  note on why a thin coordinator is a different risk shape than D2's
  fan-out cap was designed to catch.
