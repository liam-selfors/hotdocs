# Spec Scaffolder — Non-Functional Constraints

- **No network access and no model calls.** Pure filesystem work, plus
  read-only `git log` for `record_commit`.
- **Writes only under `<repo_root>/specs/`.** Never commits, never
  stages, never touches `gen/` or `verification/`.
- **Never overwrites.** A target file or directory that already exists is
  an error, except the frontmatter lines `ratify` and `record_commit` are
  defined to change.
- **Deterministic.** Given the same files on disk and the same
  arguments, the same bytes are written.
