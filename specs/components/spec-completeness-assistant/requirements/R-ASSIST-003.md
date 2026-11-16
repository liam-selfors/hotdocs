# R-ASSIST-003

**R-ASSIST-003** — For each component in the predicted blast radius, in
  order, `assist` MUST call `spec-reviewer`'s `check([component_id],
  repo_root)` with no other argument — so `model` is `None` and
  `write_proposals` `False` — and store its `to_dict()` under that
  component's id in `criterion_reviews`. A `check` that raises stores
  `{"error": str(exc)}` for that component instead and the run
  continues. This cheap preview makes no model call, with or without a
  configured `model`.
