# R-GATE-005

**R-GATE-005** — MUST invoke `license-scanner` and `secret-scanner`
  unconditionally for this component — never toggle-gated (per the
  original brainstorm's compliance-gate posture). This call and
  `R-GATE-002`'s generation call MAY run in parallel with each other
  (same brainstorm's cache/parallelize-for-cost posture) — they have no
  sequential dependency on each other given the same inputs.
