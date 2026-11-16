# R-SCAFFOLD-003

**R-SCAFFOLD-003** — `ratify(repo_root, decision_id)` MUST change the
  record's frontmatter line `status: draft` to `status: ratified` and add
  the line `last_ratified_commit: PENDING-COMMIT` as the last frontmatter
  line, leaving every other line unchanged. When the record has a
  `supersedes: <id>` line, it MUST also change that superseded record's
  `status:` line to `status: deprecated`, changing nothing else in it.
  It returns the paths changed, the record first. It MUST raise
  `LookupError`, changing nothing, when the record has no file or is
  already ratified.
