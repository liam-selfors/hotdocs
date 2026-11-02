# R-AUTHOR-013

**R-AUTHOR-013** — The prompt MUST instruct that a synthetic fixture
  (`R-AUTHOR-012`) SHOULD default to `sealed: true` (short, fake
  `source_path` not under `gen/`) unless the criterion specifically
  concerns `realizes`/capability-linkage: sealed exempts it from
  `realizes` and the capability machinery, sidestepping a whole
  `spec-linter` rule class (`R-LINT-006`). Only when a criterion
  genuinely needs `realizes`-driven behavior MUST the fixture supply a
  resolvable `P-<id>` (`D103`).
