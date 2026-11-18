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

  **Exactly four mutation operators, one mutant per site** (`D159`),
  with these exact swaps (`D172`) — the bar was calibrated against them,
  so a regeneration MUST NOT change them: a comparison with exactly one
  operator has it swapped `==`↔`!=`, `<`↔`>=`, `>`↔`<=`, `is`↔`is not`,
  `in`↔`not in` (a chained comparison is not a site); an `and`/`or`
  flipped to the other; a binary `+`↔`-`, `*`↔`/`, `//`↔`%`; a boolean
  constant negated. Never numeric constants or anything else.
