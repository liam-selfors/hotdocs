# R-COMPILE-012

**R-COMPILE-012** — The compiler MUST expose a public primitive that
  compiles one already-parsed `compiled`-kind criterion directly — no
  directory scanning, no file I/O, no assumption that the criterion
  lives under any one component's `acceptance/` — for callers compiling
  content that doesn't fit `compile`'s own "one component's
  `acceptance/` directory" scope. `compile` (`R-COMPILE-001`–`011`)
  MUST itself be implemented in terms of this primitive for each
  criterion it finds, never a second, duplicated compilation path.

  This primitive's interface surface (`surface`) MUST be optional: a
  criterion black-box against more than one component — a
  product-capability scenario, never scoped to one component's own
  `interface/` contract (`capability-scenario-verifier`'s
  `R-SCENARIO-001`, the real first caller this closes a gap for) — has
  no single surface to resolve against at all. A literal-only step
  (e.g. `Given a foo is "x"`) never needed a surface regardless; a step
  that *does* reference a function/type with no surface supplied MUST
  still be a located compile error (`R-COMPILE-002`'s own discipline,
  unchanged), never silently skipped for lack of one.

  Found missing only once a real second consumer
  (`capability-scenario-verifier`) actually needed to compile criterion
  content outside any component's `acceptance/` directory and
  `compile`'s own public surface had no way to serve that need without
  inventing a second, duplicate compilation path — exactly the
  "no new dispatch machinery" rule `R-SCENARIO-001` itself states
  (`D59`).
