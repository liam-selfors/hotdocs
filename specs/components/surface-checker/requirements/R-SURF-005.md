# R-SURF-005

**R-SURF-005** — For each asset the component declares in its
  `component.md` frontmatter `assets:` line, in declaration order,
  `check_surface` MUST find the kind's adapter by path as
  `specs/architecture/asset-kinds.md`'s Lookup gives, run its
  `surface(<code_dir>/<path>)` in a subprocess and compare the returned
  `names` with the names the asset's interface file
  `interface/assets/<file name>.md` states, exactly as check 4 of
  `interface/library.md` gives (`D343`). Each distinct stated name not
  provided, and each failure, gives check 4's finding and message; the other assets are still checked. This check runs
  only when the import check (`R-SURF-001`) found nothing.
