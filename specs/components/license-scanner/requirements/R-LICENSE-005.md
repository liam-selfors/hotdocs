# R-LICENSE-005

**R-LICENSE-005** — `gate_version` MUST be
  `license_scanner@4.0.<V>+<H>` when the scan was evaluated, `<V>` being
  the reference corpus's `corpus_version` and `<H>` the first 12 hex
  digits of the SHA-256 of its exact bytes, and
  `license_scanner@4.0.0-<reason>` (e.g. `0-no-reference-corpus`) when
  it was not (`R-LICENSE-010`). So a not-evaluated result and an
  evaluated one never share a cache key (`D30`) or a provenance match,
  and any change to the corpus, with or without a version bump,
  invalidates every cached result.
