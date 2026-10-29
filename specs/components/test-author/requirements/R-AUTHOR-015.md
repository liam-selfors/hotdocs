# R-AUTHOR-015

**R-AUTHOR-015** — The prompt MUST instruct that whenever a test
  constructs a synthetic fixture (`R-AUTHOR-012`) and the criterion
  depends on a precondition the target checks against `spec-linter`,
  the test MUST call `lint()` against the fixture first and assert
  zero hard-fail findings before exercising the real behavior — a MUST
  (`D110`), not a SHOULD left to model judgment: self-check alone is
  necessary but not sufficient (`R-AUTHOR-020`).

  **MUST include the exact call as a literal worked snippet, not
  prose** (`D117`): `lint(None, repo_root)` — `paths` first,
  positionally `None`, never just one positional argument. Stating
  the real signature in prose alone was not enough, even corrected
  (`D116`).

  A standing safeguard (`D104`): every `R-AUTHOR-012`–`014` failure
  surfaced as a confusing deep failure, not an immediate signal.
