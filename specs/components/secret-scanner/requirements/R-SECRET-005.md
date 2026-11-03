# R-SECRET-005

**R-SECRET-005** — Before scanning, the scanner MUST check
  `cache-manager` using key `(spec_bundle_hash, gate_inputs_hash,
  gate_version, model_pin)` — `cache-manager`'s own canonical field
  names (`interface/data/CacheKey.md`). `spec_bundle_hash` is
  `"sha256:"` plus the hash of the scanned files under `specs/`;
  `gate_inputs_hash` is `"sha256:"` plus the hash of all other scanned
  files, which includes the allowlist (`R-SECRET-012`); `model_pin` is
  `"none"`. A file set's hash covers each file's relative path and
  content, in sorted path order. On a cache hit the cached result MUST
  be reused. Caching is best-effort: a cache failure never fails or
  alters a scan.
