# Decision Drift Detector — Non-Functional Constraints

- **No network access, no model calls.** Pure git/filesystem reads
  against the local repository.
- **Never gates anything.** Purely diagnostic — see
  `specs/architecture/pipeline-decomposition.md`'s "Advisory tooling"
  table. No mechanism anywhere calls this component as a merge
  precondition.
- **Ancestry, never timestamps.** `R-DRIFT-002`'s ordering check is
  always `git merge-base --is-ancestor`, never a commit-date
  comparison — a non-linear history has no trustworthy linear order
  by date alone.
- **A missing or unreadable git history is a usage error, not a
  silent empty report.** If `repo_root` is not a git repository, or a
  cited file has no commit history at all (uncommitted), this MUST
  fail loudly (exit `2`), never report zero drift as if the check
  actually ran.
