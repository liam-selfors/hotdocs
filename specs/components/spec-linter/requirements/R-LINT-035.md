# R-LINT-035

**R-LINT-035** — `lint(..., strict=True)` MUST count `warn` findings in
  `hard_failures` as well as `fail` ones. `main(argv)` MUST implement
  `interface/cli.md`: lint the given paths, else all of `specs/` under
  `--repo-root`, passing `--strict` on as `strict`; print the report as
  text, or with `--format=json` as the `LintReport` JSON; and return the
  exit code its table gives from `hard_failures`.
