# R-PROV-021

**R-PROV-021** — Every value `write_provenance` and
  `write_sealed_provenance` write MUST first be converted exactly as
  `specs/architecture/json-values.md` gives, so no value an input holds,
  such as a `set` in a failing criterion's `failure_detail.actual`, makes
  a write raise (`D318`).
