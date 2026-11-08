# R-PACKET-013

**R-PACKET-013** — `build_review_packet` MUST load `provenance-tracker`
  from `<repo_root>/gen/provenance-tracker/` when that directory
  exists, and otherwise from the same path under the tool root: the
  parent of the nearest directory named `gen` above this module's own
  file (`D199`). A project made by `hotdocs init` has no copy of the
  tool's components.
