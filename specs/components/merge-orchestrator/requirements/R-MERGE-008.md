# R-MERGE-008

**R-MERGE-008** — MUST invoke `license-scanner` and `secret-scanner`
  unconditionally for every impacted component — never toggle-gated
  (per the original brainstorm's compliance-gate posture). This call and
  R-MERGE-004's generation call MAY run in parallel with each other per
  component (same brainstorm's cache/parallelize-for-cost posture) —
  they have no sequential dependency on each other given the same
  inputs.
