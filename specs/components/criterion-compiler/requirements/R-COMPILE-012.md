# R-COMPILE-012

**R-COMPILE-012** — The compiler MUST expose a public primitive that
  compiles one already-parsed `compiled`-kind criterion directly — no
  directory scanning, no file I/O, no assumption that the criterion
  lives under any one component's `acceptance/` (`D59`). `compile` (`R-COMPILE-001`–`011`)
  MUST itself be implemented in terms of this primitive for each
  criterion it finds, never a second, duplicated compilation path.

  This primitive's interface surface (`surface`) MUST be optional: a
  criterion black-box against more than one component — a
  product-capability scenario, never scoped to one component's own
  `interface/` contract — has no single surface to resolve against. A
  literal-only step (e.g. `Given a foo is "x"`) compiles without one; a step
  that *does* reference a function/type with no surface supplied MUST
  still be a located compile error (`R-COMPILE-002`'s own discipline,
  unchanged), never silently skipped for lack of one.
