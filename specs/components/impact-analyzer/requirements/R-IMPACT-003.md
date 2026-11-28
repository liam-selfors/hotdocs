# R-IMPACT-003

**R-IMPACT-003** — For a changed component whose `interface/cli.md`,
  `interface/library.md`, or any file under `interface/data/` changed
  relative to the prior commit (each compared independently; a file added
  or removed counts as changed) — **excluding `interface/guarantees/`,
  which R-IMPACT-008 handles separately and may narrow** — the analyzer
  MUST include every component with a `depends_on` edge to it, tagged with
  reason `transitive-interface`, naming the upstream component whose
  interface changed. These three file kinds always propagate in full,
  unconditionally (`D2`).
