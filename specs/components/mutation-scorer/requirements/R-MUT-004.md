# R-MUT-004

**R-MUT-004** — When the baseline fails, `score` MUST run each test file
  alone in the same sandbox with the 300-second timeout; each that fails
  alone is listed in `faulty_tests`, and the baseline runs again
  without them (`mutation-runs.md`, "Faulty tests"). With no file left,
  `mutation_score` and `mutation_error` are both `null`. When none fails
  alone, or the second baseline fails too, `mutation_error` is the
  baseline's message.
