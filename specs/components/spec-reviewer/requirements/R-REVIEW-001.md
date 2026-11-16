# R-REVIEW-001

**R-REVIEW-001** — `check` MUST resolve `targets` to criteria: a component
  id `comp-<slug>` gives every `AC-*.md` file under
  `<repo_root>/specs/components/<slug>/acceptance/`, sorted by id; a
  criterion id gives that one criterion, from whichever component holds
  it. The union, de-duplicated and sorted, is `criteria_checked`. A
  target that names no component directory and no criterion file MUST
  raise `ValueError` before any dependency is called.
