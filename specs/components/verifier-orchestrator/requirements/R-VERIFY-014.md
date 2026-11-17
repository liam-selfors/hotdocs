# R-VERIFY-014

**R-VERIFY-014** — Every test run MUST have a wall-clock timeout,
  killing the whole process tree: 300 seconds for a run on unmutated
  code, whose timeout fails that criterion. Mutation runs MUST follow
  `specs/architecture/mutation-runs.md`: only passing criteria's tests,
  a copy at `<tmp>/gen/<slug>/` beside links to every other `gen/`
  directory, that copy as working directory and `PYTHONPATH`, with
  `--noconftest` (`D159`, `D280`), and an unmutated baseline that must
  pass before any mutant runs and sets each mutant's timeout (`D158`,
  `D324`).
