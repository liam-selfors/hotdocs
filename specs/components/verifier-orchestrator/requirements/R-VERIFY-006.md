# R-VERIFY-006

**R-VERIFY-006** — The mutation score MUST be `mutation-scorer`'s
  `score(component_id, repo_root, tests, environment)`, `tests` the
  files of the `generated-test` criteria whose `result` is `pass`, in
  criterion order, and `environment` the run environment
  (`R-VERIFY-020`, `D383`). The overall verdict MUST be `fail` when its
  `mutation_error` is set, or when the score falls below 0.8, or 0.9
  when a `generated-test` criterion is freeform-derived, written with
  no Given/When/Then block (`specs/architecture/acceptance-criteria.md`,
  `D80`).
