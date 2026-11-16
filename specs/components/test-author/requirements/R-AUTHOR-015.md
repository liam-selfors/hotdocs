# R-AUTHOR-015

**R-AUTHOR-015** — The prompt MUST instruct that whenever a test
  constructs a synthetic fixture (`R-AUTHOR-012`) and the criterion
  depends on a precondition the target checks against `spec-linter`,
  the test MUST call `lint()` against the fixture first and assert zero
  hard-fail findings before exercising the real behavior (`D110`);
  The prompt MUST include the exact call as a literal worked snippet,
  not prose: `lint(None, repo_root)` — `paths` first, positionally
  `None`, never one positional argument (`D116`/`D117`). Otherwise an
  `R-AUTHOR-012`–`014` failure surfaces as a confusing deep failure
  (`D104`).
