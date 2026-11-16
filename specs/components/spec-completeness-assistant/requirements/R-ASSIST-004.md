# R-ASSIST-004

**R-ASSIST-004** — MUST produce a completeness confidence score (0.0–1.0)
  with structured rationale from one model call whose prompt holds: for
  each changed requirement, its full text followed by the full text of
  each of its covering criteria, or the line
  `No acceptance criterion covers <R-id>.` when it has none; the
  `invisible_reference` findings in `criterion_reviews` for the changed
  components; and every `lint_findings` entry for a file in a changed
  component. The prompt asks whether each changed requirement's criteria
  check what it states, whether a dependent's `interface/` looks like it
  needs a matching update that was not made, and whether a criterion
  expects behavior no requirement states.
