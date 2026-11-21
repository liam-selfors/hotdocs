# R-REVIEW-003

**R-REVIEW-003** — For each criterion, `check` MUST build its bundle with
  `assemble_criterion` and collect the tokens of its `When` and `Then`
  steps. The steps are the lines between the `` ```gherkin `` line and the
  next `` ``` `` line of the bundle's `criterion_text`; a step starts at a
  line whose first word is `Given`, `When` or `Then`, and every following
  line, `And`, `But` or indented, belongs to it. A token is the text of an
  inline code span on one line, a single backtick, text with no backtick,
  a single backtick, with surrounding spaces removed; when it contains
  `<`, only the text before the first `<` is kept, and an empty token is
  skipped. For each distinct token appearing nowhere in the concatenation
  of the bundle's `requirement_text`, `interface`, `glossary` and every
  value of `dependency_interfaces`, `check` reports one
  `invisible_reference` finding whose `token` is that token and whose
  `message` is
  `` `<token>` appears in <criterion_id> but not in what its test author sees``.
  Findings are ordered by criterion id, then by the token's first
  position. A token in a `Given` step, or outside the block, is never
  reported: the criterion supplies it.
