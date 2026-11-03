# R-SECRET-008

**R-SECRET-008** — The scanner MUST support a lightweight invocation
  for a pre-commit/pre-push hook, scoped only to the given files, not
  the whole repository, with no `cache-manager` dependency (nothing
  stable exists yet to key a cache entry on). It uses the same engine,
  plugin set, skip rules, and result shape as a full scan, with
  `scope` `"precommit"`. When given a `repo_root`, it reports each
  path relative to it and applies the allowlist (`R-SECRET-012`)
  exactly as a full scan does; given none, it reports paths as given
  and applies no allowlist.
