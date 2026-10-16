# R-LINT-017

**R-LINT-017** — The linter MUST verify every file under a component's
  `interface/guarantees/` directory has a unique `G-<comp>-NNN` id
  (matching its own filename, per D16, the same way `requirements/` files
  do per R-LINT-007) and uses at least one RFC 2119 keyword — a guarantee
  is a normative promise to a dependent, not descriptive prose.
