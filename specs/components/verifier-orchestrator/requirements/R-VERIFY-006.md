# R-VERIFY-006

**R-VERIFY-006** — For `generated-test`-kind criteria, this component MUST
  compute and report the mutation score, and the overall verdict MUST be
  `fail` if it falls below 0.8, or 0.9 when a `generated-test` criterion
  is freeform-derived, written with no Given/When/Then block
  (`SPEC_GUIDELINES.md` §5, `D80`).

  **One score for the whole component, never an average** (`D124`):
  each mutant is generated once and counts as killed if *any*
  `generated-test` file fails against it.

  The sites, swaps and the check for JavaScript in a Python string are
  exactly those of `specs/architecture/mutation-runs.md`: the `python`
  adapter's strength sites (`D159`, `D172`, `D344`), then each declared
  asset's (`D343`). The bar was calibrated against them, so a regeneration MUST
  NOT change them.
