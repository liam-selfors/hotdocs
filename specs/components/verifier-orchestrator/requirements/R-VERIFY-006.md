# R-VERIFY-006

**R-VERIFY-006** — For `generated-test`-kind criteria, this component MUST
  compute and report the mutation score, and the overall verdict MUST be
  `fail` if it falls below 0.8, or 0.9 when a `generated-test` criterion
  is freeform-derived, written with no Given/When/Then block
  (`SPEC_GUIDELINES.md` §5, `D80`).

  **A single score for the whole component, a union across all of its
  own `generated-test` criteria's test files — never an average of
  per-criterion scores** (`D124`): generate each mutant once, against the
  whole candidate module; it counts as killed if *any* of those test
  files fails against it. `VerificationReport.mutation_score` is exactly
  one number per component (`interface/data/VerificationReport.md`).

  **Exactly four mutation operators, one mutant per site** (`D159`),
  with these exact swaps (`D172`) — the bar was calibrated against them,
  so a regeneration MUST NOT change them: a comparison with exactly one
  operator has it swapped `==`↔`!=`, `<`↔`>=`, `>`↔`<=`, `is`↔`is not`,
  `in`↔`not in` (a chained comparison is not a site); an `and`/`or`
  flipped to the other; a binary `+`↔`-`, `*`↔`/`, `//`↔`%`; a boolean
  constant negated. Never numeric constants or anything else.
