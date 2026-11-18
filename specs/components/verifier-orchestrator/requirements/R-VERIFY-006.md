# R-VERIFY-006

**R-VERIFY-006** — For `generated-test`-kind criteria, this component MUST
  compute and report the mutation score, and the overall verdict MUST be
  `fail` if it falls below 0.8, or 0.9 when a `generated-test` criterion
  is freeform-derived, written with no Given/When/Then block
  (`SPEC_GUIDELINES.md` §5, `D80`).

  **One score for the whole component, never an average** (`D124`):
  each mutant is generated once, against the whole candidate module, and
  counts as killed if *any* of the `generated-test` files fails against
  it.

  **The mutation sites and swaps are exactly those of
  `specs/architecture/mutation-runs.md`**, one mutant per site
  (`D159`, `D172`): Python's four operators, and the token swaps inside
  a string literal holding JavaScript (`D335`). The bar was calibrated
  against them, so a regeneration MUST NOT change them.
