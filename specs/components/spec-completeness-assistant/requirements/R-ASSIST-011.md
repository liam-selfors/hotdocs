# R-ASSIST-011

**R-ASSIST-011** — On every call, `assist` MUST load each dependency
  separately from `<repo_root>/gen/<slug>/` when that dependency's own
  directory exists, and otherwise from the same path under the tool
  root: the parent of the nearest directory named `gen` above this
  module's own file (`D199`). It MUST NOT reuse a module loaded by an
  earlier call or found in `sys.modules`. A project made by
  `hotdocs init` has no copy of the tool's components.
