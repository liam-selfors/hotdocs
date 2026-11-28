# R-LINT-011

**R-LINT-011** — The linter MUST fail a `Definitions`-section entry for a
  glossary term whose local text is **near-verbatim identical** (normalized
  token-overlap ratio ≥ 0.8 against the glossary's own definition text) to
  `specs/glossary.md`'s definition.
  This is a textual-similarity check only: deterministic, no model call, no
  judgment of meaning.
