# R-SURF-003

**R-SURF-003** — When the component's `interface/library.md` has an
  `Implements:` line naming `specs/architecture/cli-conventions.md`,
  `check_surface` MUST run, in a subprocess of `R-SURF-006`'s
  interpreter,
  `sys.exit(<module>.main(["--hotdocs-smoke-unknown"]))`. Unless it exits
  `2`, with a first stderr line starting `usage error: `, and with
  `Traceback` nowhere in stderr, it gives one `cli_usage` finding naming
  what differed: `exit <code>`, `no usage error line`, or `traceback`,
  joined by `, `. A timeout gives `cli_usage` with message `timeout`.
