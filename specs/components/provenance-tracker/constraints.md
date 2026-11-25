# Provenance Tracker — Non-Functional Constraints

- **No model calls, and no network access but `secret-scanner`'s own
  webhook (`R-TRACK-016`), for the component half of
  `check_readiness`.** The component check reuses `provenance-checker`'s
  own deterministic logic and never calls `component-gate-runner`
  (`D93`). The capability half may make real model calls, through
  `capability-scenario-verifier`'s `run_capability_gates`, on a
  capability miss — that cost is `capability-scenario-verifier`'s own,
  incurred inside its own real function call, not this component's.
- **Never an automated gate input.** `hotdocs verify` answers a
  question; no component's own pass/fail decision reads this
  component's output, and nothing enforces that a developer ran it
  before committing (`D87`). Running it over the full blast radius of
  what was regenerated, before committing, is a workflow MUST (`D99`)
  that this component does not enforce.
- **`AttemptRecord` is append-only, never mutated.** Once written, it
  MUST NOT be edited or deleted by this component — history is the
  entire value of this data.
- **Determinism of assembly, not of the capability half's side
  effects.** Given the same mocked `ProvenanceCheckResult`/
  `CapabilityProvenanceCheckResult` and `secret-scanner` results for a scope,
  `check_readiness`'s own `VerifyReport` assembly MUST be
  byte-identical — a claim about this component's own aggregation
  logic, not a claim that two real `hotdocs verify` runs against a
  changing corpus, or against a capability that gets re-run, produce
  identical reports.
- **No retention or eviction policy.** `.hotdocs/attempts/` grows
  without bound; it is local, gitignored data a developer can delete at
  any time with no correctness consequence.
