# R-REVIEW-008

**R-REVIEW-008** — Before it calls `lint`, `check` MUST look for the
  interface file of every declared asset (`D361`). The components are
  those the targets name, a criterion id naming the component that holds
  it, in sorted order of their ids. A component's assets are read from
  its `component.md`: the first line starting with `assets:` between the
  file's first two `---` lines, the text between that line's `[` and `]`,
  split on `,`, each item stripped and split at its first `:` into kind
  and path; no such line, no `[`, or an item with no `:`, gives no asset.
  For each asset, in the order written, whose file
  `<repo_root>/specs/components/<slug>/interface/assets/<file name>.md`
  does not exist, `<file name>` being the path's text after its last `/`,
  `check` reports one finding whose `criterion_id` is the component's id,
  whose `kind` is `asset_interface_missing`, whose `token` is the path,
  and whose `message` is
  `` `<path>` has no interface file specs/components/<slug>/interface/assets/<file name>.md``.
  These findings come first in `findings`, on every return, the early
  one of `R-REVIEW-002` included.
