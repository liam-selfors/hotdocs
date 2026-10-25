# R-TRACK-006

**R-TRACK-006** — The written records MUST be queryable by DuckDB's core
  `read_json` function against a glob over `.hotdocs/tracking/*.json`
  with no transformation, conversion, or ingestion step — this is the
  entire point of the file shape `R-TRACK-002`/`003` specify. There MUST
  NOT be a bespoke query API, library function, or CLI subcommand that
  duplicates what a direct DuckDB query already does; a CLI convenience
  wrapper (`interface/cli.md`) that runs such a query on the caller's
  behalf is permitted, but it MUST NOT be the only way to read this data
  — any tool with a DuckDB client can query `.hotdocs/tracking/`
  directly, without going through this component at all.
