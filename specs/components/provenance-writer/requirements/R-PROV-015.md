# R-PROV-015

**R-PROV-015** — `main(argv)` MUST implement `interface/cli.md` exactly:
  `hotdocs provenance write <component-id> [--repo-root=<dir>]`, reading
  a JSON-encoded `ProvenanceInputs` from stdin. Exit `0` once
  `write_provenance` succeeds; exit `1` on `MissingInputError` (a
  required upstream result was absent); exit `2` on any usage error —
  wrong/missing positional arguments, an unrecognized `--` flag, a
  `--repo-root` with no value, or malformed JSON on stdin. (`D130`)
