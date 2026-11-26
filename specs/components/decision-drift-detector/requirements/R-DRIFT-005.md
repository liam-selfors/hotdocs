# R-DRIFT-005

**R-DRIFT-005** — `main(argv)` MUST implement `interface/cli.md`
  exactly: `hotdocs decision-drift [--format=json|text]
  [--repo-root=<dir>]` and `hotdocs decision-impact <decision-id>
  [--format=json|text] [--repo-root=<dir>]`. Exit `0` once a report is
  produced, regardless of whether it is empty — neither subcommand is
  a gate. Exit `2` on any usage error: not a git repository, an
  unreadable `--repo-root`, or a missing `<decision-id>` for
  `decision-impact`. `--format=json` MUST print the report as JSON
  matching its own schema; the default/`--format=text` MUST print a
  human-readable rendering.
