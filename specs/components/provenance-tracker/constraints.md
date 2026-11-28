# Provenance Tracker — Non-Functional Constraints

- **No model calls, and no network access but `secret-scanner`'s own
  webhook (`R-TRACK-016`), for the component half of
  `check_readiness`.** The component check reuses `provenance-checker`'s
  own deterministic logic and never calls `component-gate-runner`
  (`D93`). The capability half may make model calls through
  `run_capability_gates`, on a capability miss.
- **`AttemptRecord` is append-only, never mutated.** Once written, it
  MUST NOT be edited or deleted by this component.
- **Determinism of assembly, not of the capability half's side
  effects.** Given the same mocked `ProvenanceCheckResult`/
  `CapabilityProvenanceCheckResult` and `secret-scanner` results for a scope,
  `check_readiness`'s own `VerifyReport` assembly MUST be
  byte-identical.
- **No retention or eviction policy.** Never prunes `.hotdocs/attempts/`.
