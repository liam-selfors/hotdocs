# R-DOCS-007

**R-DOCS-007** — `cli.main` MUST behave as `interface/cli.md` says:
  exit `0` after rendering to `--out`, `1` when `corpus-graph.json` is
  missing or not valid JSON, and `2` on a usage error, including an
  unknown flag and a flag with no value. `argv` holds only the tokens
  after `hotdocs docs-site build`.
