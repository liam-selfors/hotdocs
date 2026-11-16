# R-ASSIST-004

**R-ASSIST-004** — MUST produce a completeness confidence score (0.0–1.0)
  with rationale from one model call, made whenever the run is not
  halted, whose prompt holds: for each changed requirement, its file's
  contents exactly as read followed by those of each of its covering
  criteria, or the line `No acceptance criterion covers <R-id>.` when it
  has none; the `invisible_reference` findings in `criterion_reviews`
  for the changed components; and every `lint_findings` entry inside a
  changed component. The prompt asks whether each changed requirement's
  criteria check what it states, whether a dependent's `interface/`
  needs a matching update that was not made, and whether a criterion
  expects behavior no requirement states, and asks for the completeness
  reply `interface/library.md` gives. `completeness_score` is the
  reply's number (clamped to 0.0–1.0) and `completeness_rationale` its
  string, verbatim.
