# R-TRACK-002

**R-TRACK-002** — The tracking record MUST include: a unique `attempt_id`;
  a `timestamp`; the `changed_ids` that triggered the attempt; the overall
  outcome (`pass` | `blocked`); `block_reasons` (empty unless blocked); and,
  per impacted component, a flattened summary — `provenance_hit`, `attempts`,
  whether the final attempt was a `model_call_error` or reached
  verification, the verification `overall` result if it reached
  verification, and whether either scanner flagged it. See
  `interface/data/TrackingRecord.md` for the exact shape.

  **Deliberately flattened, not a nested copy of `VerificationReport`/
  `LicenseScanResult`/etc.:** the full detail already exists, durably, in
  `provenance-writer`'s own output — this component's record is for
  aggregate querying (how many attempts did this component need, across
  history; how often does a merge block), not for re-deriving what a
  specific criterion checked. Keeping it flat also keeps it reliably
  columnar for DuckDB's `read_json` to infer a consistent schema across
  many files without configuration.
