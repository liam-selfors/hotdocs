# R-ASSIST-009

**R-ASSIST-009** — `main(argv)` MUST implement `interface/cli.md`
  exactly, with `argv` the tokens after `assist` (`hotdocs-cli`
  strips the verb): `--changed`
  (repeatable or comma-separated, required), `--repo-root` (default the
  current directory), `--format=json|text` (default `text`), and
  `--model` (omitted means degraded mode; given, its value is passed to
  `assist` as `model`). Each flag accepts `--flag=value` or
  `--flag value`. Exit `0` once a report is produced, `1` when the report
  has `halted` true, `2` on a usage error
  (no `--changed`, an invalid `--format`, an unknown argument, a flag
  given last with no value). `--format=json` prints the
  `CompletenessReport` as JSON; `text` prints a human-readable rendering
  naming every lint finding's `rule_id`, every predicted-blast-radius
  component with its count of `criterion_reviews` findings, and, when
  not null, a line `completeness_score: <str(value)>`.

  Covered from the start, unlike CLIs found uncovered by mutation
  testing (`D130`, `D160`).
