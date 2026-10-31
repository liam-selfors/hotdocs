# R-PACKET-007

**R-PACKET-007** — Any new or changed `sealed` or
  `gen/<component>/.overrides.json` declaration in this PR MUST appear as
  its own explicit section (principle 7/§8) — a declared exemption from the
  normal discipline is exactly the kind of thing a reviewer must see called
  out, not buried in a frontmatter diff.

  **"Changed `sealed`" means a genuine transition, detected against
  the file's own first commit in `HEAD`'s history, never against
  `R-PACKET-001`'s own PR diff-base** (`git log --follow --format=%H
  -- <path>`, oldest result = that file's own first commit reachable
  from `HEAD`; read `sealed` there and at `HEAD` via `git show
  <rev>:<path>`). This is deliberately a *different* comparison point
  than `spec_diff`'s own base: the PR diff-base is sometimes the
  empty tree (`R-PACKET-001`'s own fallback for "no feature branch"),
  against which *every* file in the repo reads as "doesn't exist" —
  using it here would either flag every already-sealed component as
  newly sealed (treating "doesn't exist at base" as "not sealed
  there") or exclude every genuine transition more than one commit
  back (requiring the file to exist at that same base). Comparing
  each file against *its own* first commit sidesteps both failure
  modes at once, regardless of how many commits separate that
  transition from `HEAD` or whether a feature branch exists:
  `sealed: false`/absent at that first commit and `sealed: true` at
  `HEAD` is the transition; `sealed: true` already at that first
  commit (the component was sealed from birth) is not. A brand-new
  `gen/<component>/.overrides.json` keeps the simpler, original rule
  — its mere existence at `HEAD` and absence at `R-PACKET-001`'s own
  PR diff-base **is** the complete signal, since an override file has
  no in-file "unsealed" state to transition from and a reviewer does
  need to see every override newly introduced *in this PR*, not
  merely ever.

  **Both are discovered entirely from the git diff's own file paths**
  (`specs/components/<slug>/component.md`, `gen/<slug>/.overrides.json`)
  — never filtered against, or restricted to, `changed_ids`. Unlike
  `changed_requirements` (`R-PACKET-002`, a simple filter *of*
  `changed_ids`), a sealed/override change can affect a component
  `changed_ids` never named at all (the caller's list is about blast
  radius, not about which `component.md`/`.overrides.json` files
  this diff happens to touch) — restricting the scan to
  `changed_ids` would silently miss a real exemption declared on any
  component not literally present in that list.
