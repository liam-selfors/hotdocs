# R-LINT-016

**R-LINT-016** — The linter MUST fail any unit file (under a component's
  `requirements/`, `interface/` — including `interface/data/` — or
  `acceptance/`, or its `constraints.md`) that carries a YAML frontmatter
  block at all. Frontmatter lives only on a component's `component.md`
  (D1, `SPEC_GUIDELINES.md` §2); a unit file's identity is its filename,
  with nothing left for frontmatter to declare, so finding one is a
  structural violation, not a missing-field one (that's R-LINT-001's job,
  and only applies to root-level documents).
