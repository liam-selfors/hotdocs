# R-LINT-031

**R-LINT-031** — For every component with a CLI document under
  `interface/`, the linter MUST warn unless one of that component's
  requirements cites that document by its relative path and a
  criterion covers that requirement. The finding names the component
  id (`comp-<slug>`) and points at `specs/architecture/acceptance-criteria.md`. Warn only (`D162`).
