# R-ASSIST-009

**R-ASSIST-009** — `main(argv)` MUST implement `interface/cli.md`
  exactly, with `argv` beginning `["assist", ...]`: `--changed`
  (repeatable or comma-separated, required), `--repo-root` (default the
  current directory), `--format=json|text` (default `text`), and
  `--model` (omitted means degraded mode; given, its value is passed to
  `assist` as `model`). Each flag accepts `--flag=value` or
  `--flag value`. Exit `0` once a report is produced, `1` when any
  `lint_findings` entry has `severity` `"fail"`, `2` on a usage error
  (no `--changed`, an invalid `--format`, an unknown argument, a flag
  given last with no value). `--format=json` prints the
  `CompletenessReport` as JSON; `text` prints a human-readable rendering
  naming every lint finding's `rule_id`, every predicted-blast-radius
  component, and, when present, the `completeness_score`.

  Covered from the start of its own repair rather than discovered again
  later: three other components' CLIs went uncovered until mutation
  testing exposed them (`D130`, `D136`, `D145`), and this one did too
  (`D160`).
