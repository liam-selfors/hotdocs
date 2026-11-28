# R-LINT-014

**R-LINT-014** — The linter MUST fail if more than one glossary-like file
  exists under `specs/` without a corresponding `architecture/`-level
  bounded-context split decision (`notes/initial-ideas.md`'s own D14): a
  file under `specs/architecture/` whose body contains `bounded context`
  or `bounded-context`, case-insensitively. The glossary-like files
  are `load_corpus`'s `glossary_files` (`specs/glossary*.md`); each one
  but `specs/glossary.md` gets one finding.
