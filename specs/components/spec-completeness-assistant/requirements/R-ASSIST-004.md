# R-ASSIST-004

**R-ASSIST-004** — MUST produce a completeness confidence score (0.0–1.0)
  with structured rationale: whether touched requirements have present,
  non-trivial acceptance criteria; whether a dependent's `interface.md`
  looks like it needs a matching update that wasn't made; whether the
  change's `Definitions` entries conflict with the glossary (reusing
  `spec-linter`'s R-LINT-011/015 distinction — this component does not
  reimplement that detection, it surfaces `spec-linter`'s own findings
  plus whatever this component's own broader judgment adds on top).
