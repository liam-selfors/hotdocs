# R-DOCS-007

**R-DOCS-007** — `cli.main` MUST behave as `interface/cli.md` says:
  exit `0` after rendering to `--out`, `1` when `corpus-graph.json` is
  missing or not valid JSON, and `2` on a usage error, including an
  unknown flag and a flag with no value. `argv` holds only the tokens
  after `hotdocs docs-site build`. When the file is missing, it MUST
  print to stderr exactly one line, `error: <path> is missing; run hotdocs
  corpus-graph build first`, on a single line with `<path>` the path
  it looked for, ending in `verification/corpus-graph.json`
  (`D366`).
