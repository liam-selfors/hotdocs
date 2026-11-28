# R-LINT-010

**R-LINT-010** — The linter MUST fail any acceptance criterion missing a
  `kind` or a complete Given/When/Then block, with at most one finding
  for each, `file` the criterion's file and `line` `1`:
  `<id> has no Kind: line (compiled, generated-test or llm-judge)`, and
  `<id> lacks a complete Given/When/Then block (missing <words>)`,
  `<words>` the missing ones of `Given`, `When`, `Then` in that order,
  joined by `, `. A criterion has the block when, for each word, some
  line of its file, stripped, starts with it.
