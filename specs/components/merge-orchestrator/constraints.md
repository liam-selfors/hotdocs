# Merge Orchestrator — Non-Functional Constraints

- **Determinism of sequencing, not of everything sequenced.** Given the
  same mocked dependency outputs, this component's own call order and
  blocking decisions MUST be reproducible — the same conditional structure
  every other coordination component in this corpus (`verifier-orchestrator`)
  already follows.
- **Fail fast, cheapest gate first.** `spec-linter` (R-MERGE-001) MUST run
  before any component that costs a model call — this ordering is itself a
  constraint, not an implementation detail, since getting it backward would
  burn generation cost on specs that were never going to lint clean.
- **No gate skipped silently.** A cache hit (R-MERGE-003) skips real work,
  but MUST be visible in `MergeResult` and the review packet — never
  indistinguishable from "this gate ran and found nothing."
- **This component's own fan-out (14 dependencies, `golden-scenario-
  verifier` replacing `criterion-compiler` after D25's extraction) is
  accepted, not a defect** — see `specs/architecture/
  pipeline-decomposition.md`'s dedicated note on why a thin coordinator is
  a different risk shape than D2's fan-out cap was designed to catch, and
  why extracting `golden-scenario-verifier` (D25) relieved the word-count
  cap without moving this number.
- **Golden-scenario failure is its own result category, never conflated
  with a component's own verification result.** (R-MERGE-014,
  `golden-scenario-verifier`'s `GoldenScenarioReport`) A cross-component
  finding and a single-component finding point a developer to different
  places to fix the problem — collapsing them into one undifferentiated
  "something failed" would undo the whole point of having a separate
  gate.
