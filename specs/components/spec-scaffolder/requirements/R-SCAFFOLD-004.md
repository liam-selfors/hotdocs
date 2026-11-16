# R-SCAFFOLD-004

**R-SCAFFOLD-004** — `record_commit(repo_root, decision_id, commit=None)`
  MUST replace the record's `last_ratified_commit: PENDING-COMMIT` line
  with `last_ratified_commit: <commit>` and return `<commit>`. With no
  `commit` given it MUST use the output, stripped, of
  `git log -1 --format=%h -- specs/decisions/<decision_id>.md` run in
  `repo_root`. It MUST raise `LookupError`, changing nothing, when the
  record has no file, is not ratified, already holds a value other than
  `PENDING-COMMIT`, or, with no `commit` given, git reports no commit
  touching it.
