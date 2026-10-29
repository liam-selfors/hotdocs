# R-DRIFT-001

**R-DRIFT-001** — For every live spec file (never one under
  `specs/decisions/` itself — mirroring `R-LINT-026`'s existing
  exemption), MUST extract every `D<N>` citation and, for each, walk
  `graph-query-engine`'s `edges` `supersedes` edges forward (`D74` —
  the relationship lives there, never `decision_lineage`, which
  carries only `last_ratified_commit`) to the latest decision (by
  ratification order, not citation order) that transitively
  supersedes it, if any. A citation with no superseder in its chain
  is never a candidate.

  **Edge direction, literally** (`interface/data/Edges.md`): for a
  `supersedes` edge, `source_id` is the newer decision (the one whose
  own frontmatter carries `supersedes: [...]`), `target_id` is the
  older, cited one — e.g. `('D31', 'D17', 'supersedes')` when `D31`
  supersedes `D17`, never the reverse.

  **Citation extraction MUST use the literal pattern `\bD\d+\b`**
  (`D134`) — the exact regex `spec-linter`'s own `R-LINT-026` check
  uses, matching a bare `D<N>` as a word regardless of surrounding
  backticks or punctuation. Found via a real cold-generation attempt:
  a candidate instead required citations wrapped in backticks
  (`` `(D\d+)` ``), missing every bare, backtick-free `D<N>` mention —
  "the same citation shape `R-LINT-026` already validates" was stated
  abstractly and implemented too narrowly on the first attempt.
