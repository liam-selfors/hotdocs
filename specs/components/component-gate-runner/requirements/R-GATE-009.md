# R-GATE-009

**R-GATE-009** — `main(argv)` MUST implement `specs/architecture/generate-cli.md`
  exactly: both flag-value forms, the defaults, `--retry-feedback`
  split on commas, JSON and text output, exit `0` whenever the gauntlet
  concluded, `1` when `block_reason` is `"model_call_error"` or
  `"test_authoring_failed"`, and `2`
  for every usage error that document lists — each detected before
  `run_component_gates` is called (`D162`).
