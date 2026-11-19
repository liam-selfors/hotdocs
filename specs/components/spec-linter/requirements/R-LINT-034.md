# R-LINT-034

**R-LINT-034** — For each component whose `component.md` frontmatter has
  `assets` (`D343`), the linter MUST
  report one `fail` finding, `file` that `component.md` and `line` the
  line of its `assets:` key, for each violation below, with exactly the
  message shown (`<entry>` the entry as written; `kind` and `path` its
  text before and after the first `:`):

  - `assets` not a list: `assets must be a list of <kind>:<path> strings`.
  - No `:`, `kind` not matching `[a-z][a-z0-9-]*` in full, or `path`
    empty: `asset '<entry>' is not <kind>:<path>`; no further check of
    that entry.
  - `path` starting with `/` or containing `\`:
    `asset '<entry>': path must be relative with / separators`.
  - A `/`-separated segment of `path` equal to `..`:
    `asset '<entry>': path contains ..`.
  - `path` ending in `.py`: `asset '<entry>': path ends in .py`.
  - Neither `<repo_root>/specs/asset-kinds/<kind>.md` nor the tool
    root's (as in R-LINT-032) exists:
    `asset kind '<kind>' has no definition`.
  - In the definition found first (repo's, then tool's), for each of
    `Layout`, `Environment`, `Surface`, `Running criteria`,
    `Strength check`, `Test author guidance`, `Generator guidance`, no
    line `## <name>`:
    `asset kind '<kind>' definition lacks section '<name>'`; or only
    whitespace before the next `## ` line or the end:
    `asset kind '<kind>' definition has empty section '<name>'`.
  - The definition is `<repo_root>`'s and `depends_on` lacks
    `comp-kind-<kind>`:
    `asset kind '<kind>' is defined in this repository; depends_on must list comp-kind-<kind>`.

  Findings follow entry order, then the order above; a kind's
  definition checks run once per component, at its first entry.
