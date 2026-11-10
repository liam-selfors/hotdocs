# R-CITE-004

**R-CITE-004** — `supersedes`/`status: deprecated` consistency
  (`D71`): (1) every `supersedes: D<N>` MUST resolve
  to a real `specs/decisions/D<N>.md`; (2) when it resolves, that file's `status` MUST be
  `deprecated` — `supersedes` means full replacement; (3) the inverse:
  every `status: deprecated` record MUST be named by at least one
  other real decision's `supersedes` field — never a standalone edit.

  Queries `nodes`/`edges`.
