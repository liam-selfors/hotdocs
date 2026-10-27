# R-MERGE-010

**R-MERGE-010** — Once every impacted component's `component-gate-runner`
  call has completed (each writing provenance via its own `R-GATE-006`
  as its last step) **and** capability-scenario verification
  (R-MERGE-014) has completed for this merge, MUST invoke
  `corpus-graph-builder` and `review-packet-builder` — both need the
  capability-scenario results to include in their output, so neither
  runs before R-MERGE-014 does.
