# R-ASSEMBLE-013

**R-ASSEMBLE-013** — `dependency_interfaces`' entry for each
  dependency MUST also resolve, one level deep, any data type that
  dependency's own `interface/` content names but does not itself
  own. For each identifier (a maximal run matching `[A-Za-z_][A-Za-z0-9_]*`)
  in the dependency's `interface/` `.md` files that it does not own as
  `interface/data/<identifier>.md`, search the whole corpus (not only the
  target's own `depends_on`) for exactly one component whose
  `interface/data/<TypeName>.md` exists; if found, append that type's
  own content to the same dependency's entry, under a clearly labeled
  heading naming the type and its real owning component — never
  merged in as if the dependency owned it. Ambiguous (more than one
  owner) or unresolved (no owner) names are skipped silently — never
  a guess. Expansion is one level only: a referenced type's own
  further references are never followed (`D114`).
