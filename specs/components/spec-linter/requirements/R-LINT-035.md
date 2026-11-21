# R-LINT-035

**R-LINT-035** — `main(argv)` MUST implement `interface/cli.md`: lint
  the given paths, else all of `specs/` under `--repo-root`; print the
  report as text, or with `--format=json` as the `LintReport` JSON; and
  return the exit code its table gives, `--strict` counting `warn`
  findings as failures.
