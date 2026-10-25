# R-LINT-024

**R-LINT-024** — A component's `Purpose` section MUST NOT cite a
  decision id (`D<N>`, bare or backtick-wrapped) — a fail-severity
  finding, not a warning. `Purpose` MUST be dependent-safe (`D34`): what
  a unit does and why it exists, never how that design was arrived at.
  Any decision citation, historical justification, or cross-reference
  to the discussion that produced the current design belongs in a
  `Rationale` section instead (`SPEC_GUIDELINES.md` §3.4) — this rule
  exists specifically so that boundary is checked mechanically, not
  left as an unenforced convention a future edit could casually
  violate.
