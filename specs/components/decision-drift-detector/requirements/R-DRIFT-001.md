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
