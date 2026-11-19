# R-VERIFY-014

**R-VERIFY-014** — Every test run MUST have a wall-clock timeout,
  killing the whole process tree: 300 seconds for a run on unmutated
  code, whose timeout fails that criterion. Mutation runs MUST follow
  `specs/architecture/mutation-runs.md` exactly: its tests, sandbox,
  working directory, `PYTHONPATH`, `--noconftest`, baseline and
  per-mutant timeouts (`D158`, `D159`, `D280`, `D324`).
