# R-IMPACT-010

**R-IMPACT-010** — "The prior commit" (`R-IMPACT-002`/`003`/`008`'s own
  phrase) MUST resolve to the merge-base between `HEAD` and the repo's
  default branch — the commit this branch actually diverged from, not
  `HEAD~1` (which is meaningless after more than one commit on the
  branch) and not the default branch's own current tip (which would
  miss changes the default branch picked up after this branch forked).
  Per-file change detection for `R-IMPACT-002`/`003`/`008` MUST be a
  real comparison of each relevant file's content at that commit against
  its current working-tree content — never inferred from the shape or
  format of a `--changed` id alone. This was a real, previously-
  unspecified gap: nothing anywhere in this corpus defined which git
  ref "the prior commit" means, and a real generated candidate, lacking
  anywhere to look it up, implemented no git comparison at all —
  instead attempting to infer interface-vs-internal from `--changed`'s
  own id shape, which can never work since every real caller (every
  `AC-IMPACT-*` criterion, a developer's own `--changed` list) only
  ever supplies component-level ids, never a finer-grained one
  (`D48`).
