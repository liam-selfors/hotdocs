# R-REVIEW-002

**R-REVIEW-002** — `check` MUST first call `lint` on the directories of
  the components the targets name. When any of its findings has severity
  `fail`, `check` MUST return at once with those findings in
  `lint_findings`, `criteria_checked` empty, no `assemble_criterion` and
  no `complete` call. Otherwise `lint_findings` holds every finding `lint`
  returned for those paths.
