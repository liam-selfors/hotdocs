# R-MERGE-017

**R-MERGE-017** — Every impacted component MUST be processed to
  completion — generation (or cache hit), verification, both scans — before
  this component evaluates R-MERGE-011's block conditions. A failure in
  one impacted component's processing MUST NOT skip, abort, or short-circuit
  processing of any other impacted component in the same merge attempt.

  **This resolves the parallelization-mechanism open question without
  forcing a specific answer to it:** whether components are processed
  sequentially or concurrently (R-MERGE-007/008's "MAY run in parallel")
  stays an implementation choice — this requirement constrains the
  *outcome* (every component attempted, every result collected) not the
  *mechanism*. What this rules out is fail-fast: stopping at the first
  component that fails and never attempting the rest. Fail-fast would mean
  a merge touching three components, where the first fails, never reveals
  whether the other two would have succeeded — exactly the information
  R-MERGE-018's free retry-via-re-run property depends on existing for
  every component, not just the first failure encountered.
