# R-CLI-006

**R-CLI-006** — `main` MUST implement `interface/cli.md` exactly: the exit codes `0` for help, `--version`, and a routed verb that returns `0`; `2` for an unknown verb or a missing component file or `main`; and a routed verb's own code otherwise (`D162`); and `2`, printing `usage error: <message>` to stderr, when a routed verb raises an exception whose class is named `ModelResolutionError` (`D296`).
