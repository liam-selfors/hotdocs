# R-DRIFT-003

**R-DRIFT-003** — `find_decision_impact(repo_root, decision_id)` MUST
  report everything that would be affected by altering or superseding
  `decision_id`, usable before it is ever ratified: (1) every decision
  whose `edges` `supersedes` or `builds_on` edge points at
  `decision_id`, walked transitively (unlike `R-DRIFT-001`'s forward
  walk toward the latest superseder, this walks *backward*, toward
  everything that depends on the one being altered); (2) every live
  spec file citing `decision_id` — unlike `R-DRIFT-001`/`002`, every
  citation, not only ones whose commit predates something.
  `decision_id` need not resolve to a real file yet.
