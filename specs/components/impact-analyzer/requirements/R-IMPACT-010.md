# R-IMPACT-010

**R-IMPACT-010** — "The prior commit" (`R-IMPACT-002`/`003`/`008`'s own
  phrase) MUST resolve to the merge-base between `HEAD` and the repo's
  default branch — not `HEAD~1` and not the default branch's own
  current tip.
  Per-file change detection for `R-IMPACT-002`/`003`/`008` MUST be a
  real comparison of each relevant file's content at that commit against
  its current working-tree content — never inferred from the shape or
  format of a `--changed` id alone. The default branch is the target
  of `refs/remotes/origin/HEAD` when that ref exists, else the local
  branch `main`, else `master`. With no such branch, or no merge-base,
  there is no prior commit and every compared file present in the
  working tree counts as added (`D48`).
