# R-LINT-032

**R-LINT-032** — When the linted `repo_root` holds `.hotdocs-tool.json`
  (a project made by `hotdocs init`), each component whose slug is also
  a directory directly under the tool root's `gen/` (the tool root
  being the parent of the nearest `gen` directory above the linter's
  own file) MUST get a `fail` finding naming that slug: the project's
  copy would shadow the tool's (`D199`).
