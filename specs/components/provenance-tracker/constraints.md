# Provenance Tracker — Non-Functional Constraints

- **No network access, no model calls for the component half of
  `check_readiness`.** The component check reuses `provenance-checker`'s
  own deterministic logic and never calls `component-gate-runner`
  (`D93`). The capability half may make real model calls, through
  `capability-scenario-verifier`'s `run_capability_gates`, on a
  capability miss — that cost is `capability-scenario-verifier`'s own,
  incurred inside its own real function call, not this component's.
- **Never a gate input.** `hotdocs verify` answers a question; nothing
  requires it to be run before a commit, and no component's own
  pass/fail decision reads this component's output (`D87`).
- **`AttemptRecord` is append-only, never mutated.** Once written, it
  MUST NOT be edited or deleted by this component — history is the
  entire value of this data.
- **Determinism of assembly, not of the capability half's side
  effects.** Given the same mocked `ProvenanceCheckResult`/
  `CapabilityProvenanceCheckResult` values for a scope,
  `check_readiness`'s own `VerifyReport` assembly MUST be
  byte-identical — a claim about this component's own aggregation
  logic, not a claim that two real `hotdocs verify` runs against a
  changing corpus, or against a capability that gets re-run, produce
  identical reports.
- **No retention/eviction policy specified here.** `.hotdocs/attempts/`
  growing without bound over a long-lived local checkout is a real,
  known cost — deliberately left unaddressed in this version, the same
  posture `cache-manager`'s own eviction-policy open question already
  has. Local, gitignored, disposable data a developer can delete at any
  time with no correctness consequence.
