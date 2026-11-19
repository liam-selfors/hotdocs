# R-ASSEMBLE-012

**R-ASSEMBLE-012** — `assemble`/`assemble_criterion` MUST read all
  corpus structure — every `component.md` frontmatter field,
  `depends_on`, the parsed contents of `requirements/`, `interface/`,
  `acceptance/`, everything `spec-linter`'s own `load_corpus` already
  parses — exclusively through that one call's returned `Corpus`/
  `Component` objects. Neither function MUST independently re-parse
  any spec file's YAML frontmatter, and MUST NOT
  introduce a new third-party dependency (a standalone YAML library,
  a Markdown parser, or similar) for anything a declared dependency
  — `spec-linter`, reached via DuckDB's own `yaml` community extension
  through its own dependency on `graph-query-engine` — already
  provides. Files `load_corpus` does not parse — `Implements:` and
  `Uses:` documents, `interface/assets/` files and asset-kind
  definitions (`R-ASSEMBLE-016`) — are content, read from disk as text.

  Found once a candidate re-parsed frontmatter with `PyYAML`, a package
  this corpus never installs (`D101`).
