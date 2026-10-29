# R-PROV-017

**R-PROV-017** — `ProvenanceInputs` (`interface/data/ProvenanceInputs.md`)
  MUST be defined as a real, importable `dataclass` in this component's
  own module — never only a type-hint name or a bare `Any` parameter
  with no corresponding class. `write_provenance`/`build_manifest`
  still accept an equivalent plain dict too (`R-PROV-014`'s dual
  access) — the dataclass is an additional, always-present
  construction path, not a replacement for it.

  Found via a real cold-generation regression (`D131`'s own next
  round): a candidate that correctly implemented `R-PROV-014`'s dual
  access reasoned it no longer needed `ProvenanceInputs` as an actual
  class and dropped it entirely, breaking every test that constructed
  one by name (`provenance_writer.ProvenanceInputs(...)`) — every
  other component in this corpus with a documented `interface/data/`
  type (`cache-manager`'s `CachedResult`, `license-scanner`'s
  `LicenseScanResult`, `secret-scanner`'s `SecretScanResult`) defines
  it as a real dataclass; this is the first time that convention was
  ever stated rather than just followed by coincidence.
