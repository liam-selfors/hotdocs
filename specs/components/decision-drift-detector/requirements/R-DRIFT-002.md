# R-DRIFT-002

**R-DRIFT-002** — For a citation with a superseder found (`R-DRIFT-001`),
  MUST resolve the citing file's own last commit touching it
  (`git log -1 --format=%H -- <path>`) and compare it against the
  superseder's `last_ratified_commit` via
  `git merge-base --is-ancestor <file_commit> <superseder_commit>`.
  A zero exit code (the file's commit IS an ancestor of — predates —
  the superseding ratification) MUST be reported as a drift candidate;
  a non-zero exit code (the file was already touched at or after the
  superseding decision, or the two commits are unrelated) MUST NOT be.
  Never a timestamp comparison — commit ancestry is the only
  trustworthy "happened-before" relationship in a non-linear history.
