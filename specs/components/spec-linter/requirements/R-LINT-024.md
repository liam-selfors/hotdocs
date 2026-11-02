# R-LINT-024

**R-LINT-024** — A component's `Purpose` section MUST NOT cite a
  decision id (`D<N>`, bare or backtick-wrapped) — a fail-severity
  finding, not a warning. `Purpose` MUST be dependent-safe (`D21`): what
  a unit does and why, never how the design was arrived at. Decision
  citations and history belong in a `Rationale` section
  (`SPEC_GUIDELINES.md` §3.4).
