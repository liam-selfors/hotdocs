# R-ASSIST-011

**R-ASSIST-011** — `assist` MUST load each dependency from
  `<repo_root>/gen/<slug>/` when that directory exists, and otherwise
  from the same path under the tool root: the parent of the nearest
  directory named `gen` above this module's own file (`D199`). A
  project made by `hotdocs init` has no copy of the tool's components.
