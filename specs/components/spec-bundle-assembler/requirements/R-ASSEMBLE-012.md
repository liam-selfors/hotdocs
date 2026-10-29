# R-ASSEMBLE-012

**R-ASSEMBLE-012** — `assemble`/`assemble_criterion` MUST read all
  corpus structure — every `component.md` frontmatter field,
  `depends_on`, the parsed contents of `requirements/`, `interface/`,
  `acceptance/`, everything `spec-linter`'s own `load_corpus` already
  parses — exclusively through that one call's returned `Corpus`/
  `Component` objects. Neither function MUST independently re-parse
  any spec file's YAML frontmatter or Markdown structure, and MUST NOT
  introduce a new third-party dependency (a standalone YAML library,
  a Markdown parser, or similar) for anything a declared dependency
  — `spec-linter`, reached via DuckDB's own `yaml` community extension
  through its own dependency on `graph-query-engine` — already
  provides.

  **Found only once a real candidate reinvented frontmatter parsing
  from scratch** (`D101`): `R-ASSEMBLE-005` already required *checking*
  that the corpus passes `spec-linter` cleanly, but nothing required
  *reusing* that same call's already-parsed result for everything else
  assembly needs, leaving room for a candidate to re-parse the same
  content independently — and reach for a package (`PyYAML`) this
  corpus has never installed, since every other component that reads
  YAML frontmatter does so through DuckDB's SQL-level extension
  instead, never a Python package.
