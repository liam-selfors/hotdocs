# R-AUTHOR-013

**R-AUTHOR-013** — The prompt MUST instruct that a synthetic fixture
  (`R-AUTHOR-012`) SHOULD default to `sealed: true` (short, fake
  `source_path` not under `gen/`) unless the criterion specifically
  concerns `realizes`/capability-linkage — sealed exempts it from
  `realizes` and the capability machinery entirely, sidestepping a
  whole `spec-linter` rule class (e.g. `R-LINT-006`). Only when a
  criterion genuinely needs `realizes`-driven behavior MUST the
  fixture supply a resolvable `P-<id>`.

  Found once `R-AUTHOR-012`'s fix surfaced the next layer (`D103`): a
  fixture had the right fields but an empty `realizes: []`.
