# R-SCAFFOLD-001

**R-SCAFFOLD-001** — `next_decision_id(repo_root)` MUST return `D<N+1>`,
  where `N` is the largest integer among files in
  `<repo_root>/specs/decisions/` named exactly `D<N>.md` (`N` one or more
  digits, no leading zero). Any other file, such as `README.md` or
  `D3-notes.md`, is ignored. With no such file, or no `specs/decisions/`
  directory, it MUST return `D1`.
