# R-SECRET-008

**R-SECRET-008** — The scanner MUST support a pre-commit/pre-push
  invocation, scoped only to the given files, with no
  `cache-manager` dependency. It uses the same engine, plugin set, skip
  rules, and result shape as a full scan, with `scope` `"precommit"`. When given a `repo_root`, it reports each
  path relative to it and applies the allowlist (`R-SECRET-012`)
  as a full scan does; given none, it reports paths as given
  and applies no allowlist.
