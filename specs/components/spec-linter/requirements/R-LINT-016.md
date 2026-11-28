# R-LINT-016

**R-LINT-016** — The linter MUST fail any unit file (under a component's
  `requirements/`, `interface/` — including `interface/data/` — or
  `acceptance/`, or its `constraints.md`) that carries a YAML frontmatter
  block at all. Frontmatter lives only on a component's `component.md`
  (D1, `specs/architecture/spec-frontmatter.md`); a unit file's identity is its filename.
