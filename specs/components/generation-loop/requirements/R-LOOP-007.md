# R-LOOP-007

**R-LOOP-007** — After each `verification_failed` attempt but the first,
  the loop MUST find every `generated-test` criterion whose `result` was
  `fail` with `failure_origin` `"implementation"` in both this attempt's
  report and the previous one's, and whose test file,
  `<repo_root>/verification/<slug>/generated-test/test_<id>.py` (`<id>`
  the criterion id lowercased, hyphens as underscores), had the same
  SHA-256 after both attempts. When another attempt follows, it MUST
  delete each such file, so that attempt authors the test again, at most
  once per criterion per run, and list the deleted criteria's ids,
  sorted, as this attempt's `reauthored_tests`; otherwise that list is
  `[]` (`specs/architecture/test-reuse.md`, `D341`).
