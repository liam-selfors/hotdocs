# R-CLI-005

**R-CLI-005** — The `init` row is special. Its module MUST be loaded from `<tool_root>/<dir>`, not from the project, since the project does not have it yet; no `--repo-root` is appended and `VAR_HOTDOCS_CONFIG` is not set; and its `main` is called with the remaining tokens plus the keyword arguments `tool_root`, `input_fn`, `output_fn`, `env`, and `cwd` that this component itself received, defaults filled in. Its return value is the exit code, as for any verb.
