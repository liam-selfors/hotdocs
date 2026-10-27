# Provenance Tracker — Non-Functional Constraints

- **No network access, no model calls in `check_readiness`.** It reuses
  `provenance-checker`'s and `capability-scenario-verifier`'s own
  deterministic checks — same posture those components already have.
- **Never a gate input.** `hotdocs verify` answers a question; nothing
  requires it to be run before a commit, and no component's own
  pass/fail decision reads this component's output (`D87`).
- **`AttemptRecord` is append-only, never mutated.** Once written, it
  MUST NOT be edited or deleted by this component — history is the
  entire value of this data.
- **Determinism of assembly.** Given the same inputs (the already-
  computed `ProvenanceCheckResult`/`CapabilityProvenanceCheckResult`
  values for a scope), `check_readiness`'s own `VerifyReport` MUST be
  byte-identical — a claim about this component's own aggregation
  logic, not a claim that two checks of a changing corpus produce
  identical reports.
- **No retention/eviction policy specified here.** `.hotdocs/attempts/`
  growing without bound over a long-lived local checkout is a real,
  known cost — deliberately left unaddressed in this version, the same
  posture `cache-manager`'s own eviction-policy open question already
  has. Local, gitignored, disposable data a developer can delete at any
  time with no correctness consequence.
