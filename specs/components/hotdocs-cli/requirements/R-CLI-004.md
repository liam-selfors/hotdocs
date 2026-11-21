# R-CLI-004

**R-CLI-004** — With no arguments, `help`, `--help` or `-h`, `main` MUST print `hotdocs <TOOL_VERSION>`, a usage line, and every verb of the table with its summary, and return `0`; `--version` prints `hotdocs <TOOL_VERSION>` and returns `0`. An unknown first word MUST print `usage error: unknown verb: <word>` and then the same verb list to stderr and return `2`. A matched verb whose `<dir>/<module>.py` exists under neither root MUST print a message naming the tool-root path, and return `2`; one whose module has no `main` MUST print that it is not available and return `2`.
