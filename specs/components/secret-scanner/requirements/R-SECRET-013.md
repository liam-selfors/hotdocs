# R-SECRET-013

**R-SECRET-013** — `propose(repo_root)` MUST return, without writing
  anything, a complete allowlist document (`R-SECRET-012`): every entry
  of the current valid allowlist, plus one new entry for each finding no
  entry covers that can validly be allowlisted — `"planted-fixture"` for
  a file under `verification/` or `specs/`, else `"public-constant"` for
  a hex-entropy finding. Findings that cannot be allowlisted, such as a
  secret in `gen/`, are returned as `ineligible`, each with `file`,
  `line`, `rule_id`. Entries sort by `file`, `type`, `hashed_secret`. An
  invalid (including unsealed) allowlist raises rather than being
  proposed over.
