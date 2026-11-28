# R-MUT-001

**R-MUT-001** — `score` MUST run every baseline and mutant exactly as
  `specs/architecture/mutation-runs.md` states, in its sandbox, working
  directory and `PYTHONPATH`, with `--noconftest`, under
  `environment`'s interpreter and plugin, each asset's file being the
  sandbox copy's (`D324`, `D344`). With no tests, nothing runs and the
  result is `mutation_score` `null`, `mutation_error` `null`, `0`
  mutants.
