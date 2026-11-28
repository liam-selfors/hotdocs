# R-PACKET-001

**R-PACKET-001** — The packet MUST include the actual spec diff for this
  change.
  Computed as the diff, over `specs/`, between the merge-base of `HEAD`
  and the repo's default branch, and `HEAD` — never a bare
  working-tree-vs-`HEAD` diff (empty once every change is committed,
  which a real PR always is by review time). **Fallback:** when that
  merge-base **is** `HEAD` itself (no divergence from the default
  branch — e.g. the PR's commits sit directly on the current branch,
  no separate feature branch exists), diff the empty tree (the
  canonical all-zero-content git object, hash
  `4b825dc642cb6eb9a060e54bf8d69288fbee4904`) against `HEAD` instead
  — never `HEAD~1`.
