# R-ASSEMBLE-015

**R-ASSEMBLE-015** — `assemble` and `assemble_criterion` MUST load
  `spec-linter` and `graph-query-engine` from `<repo_root>/gen/<slug>/`
  when that directory exists, and otherwise from the same path under the
  tool root, the parent of the nearest `gen` directory above this
  module's own file (`D199`). A project holds none of the tool's
  components, so without the fallback no project could assemble a
  bundle.
