# R-IMPACT-003

**R-IMPACT-003** — For a changed component whose `interface.md` content
  *did* change relative to the prior commit, the analyzer MUST include every
  component with a `depends_on` edge to it, tagged with reason
  `transitive-interface`, naming the upstream component whose interface
  changed.
