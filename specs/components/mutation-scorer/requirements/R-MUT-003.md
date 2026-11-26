# R-MUT-003

**R-MUT-003** — Before any baseline, `score` MUST apply
  `mutation-runs.md`'s check for language outside an asset, and run the
  baseline with a 300-second timeout; each mutant's timeout is 2
  seconds or 10 times the baseline's run time, whichever is larger. A
  failed check, baseline or adapter call ends scoring with
  `mutation_score` `null` and `mutation_error` exactly that document's
  message.
