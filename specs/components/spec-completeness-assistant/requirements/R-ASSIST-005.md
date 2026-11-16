# R-ASSIST-005

**R-ASSIST-005** — MUST run a redundancy/overlap check — does this change
  restate behavior already specified elsewhere in the corpus — matching the
  "Overlap / duplication score" metric (`notes/metrics.md`, Ideation
  phase). Judgment-based: detecting that two differently-worded passages
  describe the same behavior is semantic, not structural, the same category
  of problem `spec-linter`'s R-LINT-015 was split out for.

  Each populated entry in `redundancy_flags` MUST be `{new_requirement,
  overlaps_with, rationale}`: `new_requirement` is the draft change's own
  `R-id` (from `changed_ids`), `overlaps_with` is the pre-existing `R-id`
  it restates, and `rationale` is required — never optional — since an
  entry only ever exists here because a real judgment call actually
  fired and flagged it (unlike `VerificationReport.criteria[]`, which
  mixes ran and not-ran entries in one array, `redundancy_flags` holds
  only fired findings; `SPEC_GUIDELINES.md` §5's "an `llm-judge`
  criterion MUST emit structured rationale alongside its verdict" rule
  applies with no exception here).
