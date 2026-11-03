# R-PROV-017

**R-PROV-017** — `ProvenanceInputs` (`interface/data/ProvenanceInputs.md`)
  MUST be a real, importable `dataclass` in this component's own module,
  never only a type-hint name or a bare `Any` parameter.
  `write_provenance`/`build_manifest` still accept an equivalent plain
  dict (`R-PROV-014`); the dataclass is an additional, always-present
  construction path, as with every sibling component's documented
  `interface/data/` type (`D132`).
