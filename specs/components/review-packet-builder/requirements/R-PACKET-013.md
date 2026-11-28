# R-PACKET-013

**R-PACKET-013** — `build_review_packet` MUST load `provenance-tracker`
  from `<repo_root>/gen/provenance-tracker/` when that directory
  exists, and otherwise from the same path under the tool root: the
  parent of the nearest directory named `gen` above this module's own
  file (`D199`). A project made by `hotdocs init` has no copy of the
  tool's components. From that module it MUST call only `check_readiness` and
  `last_requirement_failures`, the two its interface names: any other
  name in its code is not its interface, and a stand-in providing only
  those two must work. Turning the reports it returns into the packet's
  JSON values is this component's own code (`D390`).
