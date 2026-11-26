# R-LINT-021

**R-LINT-021** — R-LINT-008 (forward traceability) and R-LINT-009
  (backward traceability) MUST be implemented as queries over
  `graph-query-engine`'s `nodes`/`edges` views — not
  independently-written traversal code.

  R-LINT-008 becomes: every `requirement` node MUST be the target of at
  least one `covers` edge. R-LINT-009 becomes: every `covers` edge's
  target MUST resolve to a real `requirement` or `capability` node, and
  report separately whether
  a non-resolving target looked like an `R-id`, a `P-id`, or neither.

  Implementation requirement, not behavioral. Exception: R-LINT-009's
  line-reporting stays a native scan (`nodes`/`edges` don't map a
  `CS-id` to its `product` doc).
