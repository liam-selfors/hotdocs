# R-GATE-010

**R-GATE-010** — `main` MUST take `--max-attempts`, `--mode` and
  `--allow-unisolated-exec` as `specs/architecture/generate-cli.md` says. A flag not given
  takes its value from the `[generate]` table of `<repo-root>/hotdocs.toml`
  (`max_attempts`, an integer; `mode`, a string), read with `tomllib`, and
  otherwise the default. A file value is valid exactly when it would be
  valid for its flag: `max_attempts` an integer, never a boolean, of at
  least `1`; `mode` `single` or `agentic`. An invalid file value is a
  usage error, exit `2`, naming the file, even when its flag is also
  given. `main` MUST validate every flag and file value before calling
  `run_component_gates`, so a usage error calls no dependency.
