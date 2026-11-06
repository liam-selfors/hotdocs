# R-LICENSE-009

**R-LICENSE-009** — `main(argv)` MUST implement `interface/cli.md`
  exactly: both flag forms, the default `--repo-root` and `--format`,
  JSON and text output, a plain `NOT EVALUATED: <reason>` line in text
  output whenever the result is not evaluated, exit `1` when the result
  is `blocked`, `0` otherwise (so a scan with no corpus exits `0`), and
  `2` for every usage error that document lists (`D162`).
