# R-PROV-015

**R-PROV-015** — `main(argv)` MUST implement `interface/cli.md` exactly:
  `hotdocs provenance write <component-id> [--repo-root=<dir>]`, reading
  a JSON-encoded `ProvenanceInputs` from stdin. Exit `0` once
  `write_provenance` succeeds; exit `1` on `MissingInputError` (a
  required upstream result was absent); exit `2` on any usage error —
  wrong/missing positional arguments, an unrecognized `--` flag, or
  malformed JSON on stdin.

  Found via mutation testing, not a behavioral test failure (`D130`):
  every acceptance criterion exercises `write_provenance`/
  `build_manifest` directly as a library call, none through `main()`
  itself — `interface/cli.md` documents the CLI but, until now, no
  requirement or acceptance criterion ever covered it, leaving its
  argument-parsing and exit-code branches permanently unexercised
  regardless of candidate quality.
