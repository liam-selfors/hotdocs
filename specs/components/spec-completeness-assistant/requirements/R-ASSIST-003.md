# R-ASSIST-003

**R-ASSIST-003** — For each component in the predicted blast radius,
  `assist` MUST call `spec-reviewer`'s `check([component_id], repo_root)`
  with no model and store its `to_dict()` under that component's id in
  `criterion_reviews`. A `check` that raises stores
  `{"error": "<the exception's message>"}` for that component instead and
  the run continues. This is the cheap preview of whether each affected
  component's criteria can still be written from what their test authors
  see; it makes no model call, with or without a configured `model`.
