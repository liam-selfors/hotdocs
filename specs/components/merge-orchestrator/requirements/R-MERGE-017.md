# R-MERGE-017

**R-MERGE-017** — Every impacted component MUST be processed to
  completion — generation (or cache hit), verification, both scans — before
  this component evaluates R-MERGE-011's block conditions. A failure in
  one impacted component's processing MUST NOT skip, abort, or short-circuit
  processing of any other impacted component in the same merge attempt.

  This resolves the parallelization-mechanism question without forcing a
  specific answer (rationale: `specs/decisions/D21.md`): whether
  components are processed sequentially or concurrently
  (R-MERGE-007/008's "MAY run in parallel") stays an implementation
  choice — this requirement constrains the *outcome*, not the
  *mechanism*. What it rules out is fail-fast: stopping at the first
  failing component and never attempting the rest, which would deny
  `R-MERGE-018`'s free retry-via-re-run property the information it
  depends on.
